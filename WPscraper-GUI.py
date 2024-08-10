import sys
import time
import csv
import os
import logging
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QFileDialog,
                             QTextEdit, QMessageBox, QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ScrapeWorker(QThread):
    progress = pyqtSignal(str)
    finished_domains = pyqtSignal(set)
    finished_wp = pyqtSignal(list)

    def __init__(self, keywords, num_pages, domain_output_file):
        super().__init__()
        self.keywords = keywords
        self.num_pages = num_pages
        self.domain_output_file = domain_output_file

    def run(self):
        self.progress.emit("Starting domain scraping...")
        domains = self.scrape_site_domains(self.keywords, self.num_pages, self.domain_output_file)
        self.progress.emit("Domain scraping finished. Starting WordPress version check...")
        self.finished_domains.emit(domains)

    def scrape_site_domains(self, keywords, num_pages, domain_output_file):
        all_domains = set()
        total_keywords = len(keywords)
        for idx, keyword in enumerate(keywords):
            self.progress.emit(f"Searching for keyword: {keyword} ({idx + 1}/{total_keywords})")
            try:
                search_urls = []
                for page in range(num_pages):
                    start = page * 10
                    search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&start={start}"
                    search_urls.append(search_url)

                all_links = set()
                for search_url in search_urls:
                    self.progress.emit(f"Extracting links from {search_url}")
                    all_links.update(self.extract_links_from_page_with_backoff(search_url))

                question_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&sa=X&ved=2ahUKEwjK5_jCmNGHAxX3VaQEHQgVHcEQ1QJ6BAgtEAE"
                all_links.update(self.extract_links_from_page_with_backoff(question_url))

                for link in all_links:
                    domain = urlparse(link).netloc
                    if self.is_valid_domain(domain):
                        all_domains.add(domain)
            except Exception as e:
                self.progress.emit(f"Error occurred while searching for {keyword}: {e}")

        try:
            with open(domain_output_file, 'w', encoding='utf-8') as file:
                for domain in sorted(all_domains):
                    file.write(f"{domain}\n")
            self.progress.emit(f"Found {len(all_domains)} unique sites for the provided keywords.")
        except Exception as e:
            self.progress.emit(f"Error writing to TXT file: {e}")

        return all_domains

    def extract_links_from_page_with_backoff(self, url, max_retries=5):
        delay = 2
        retries = 0
        while retries < max_retries:
            try:
                response = requests.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                links = set()
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    if href.startswith('/url?q='):
                        links.add(href.split('/url?q=')[1].split('&')[0])
                return links
            except requests.RequestException as e:
                self.progress.emit(f"Error occurred while making request to {url}: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
                retries += 1
        self.progress.emit(f"Failed to extract links from {url} after {max_retries} retries.")
        return set()

    def is_valid_domain(self, domain):
        excluded_domains = [
            'google.com', 'amazon.com', 'facebook.com', 'twitter.com',
            'linkedin.com', 'instagram.com', 'youtube.com', 'gov', 'amazon', 'google'
        ]
        parsed_domain = urlparse(domain).netloc.lower()
        return not any(excluded in parsed_domain for excluded in excluded_domains)


class WPScanWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)

    def __init__(self, domains, wp_output_file):
        super().__init__()
        self.domains = domains
        self.wp_output_file = wp_output_file

    def run(self):
        wp_sites = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for domain in self.domains:
                executor.submit(self.process_domain, domain, wp_sites)
        self.finished.emit(wp_sites)

    def process_domain(self, domain, wp_sites):
        site_url = f"http://{domain}"
        is_wp, version = self.is_wordpress_site(site_url)
        if is_wp:
            wp_sites.append({'site': domain, 'version': version})
        self.progress.emit(f"Checked WordPress version for {domain}")

    def is_wordpress_site(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            content = response.text.lower()

            if any(indicator in content for indicator in ['/wp-content/', '/wp-admin/', '/wp-json/', '/wp-login/']):
                soup = BeautifulSoup(response.text, 'html.parser')
                meta_tag = soup.find('meta', attrs={'name': 'generator'})
                if meta_tag and 'wordpress' in meta_tag.get('content', '').lower():
                    version = meta_tag['content'].split()[-1]
                else:
                    version = 'Unknown'
                return True, version

            if self.check_common_wp_files(url) or self.check_wp_rest_api(url):
                return True, 'Unknown'
            return False, None
        except (requests.RequestException, Exception) as e:
            logging.error(f"Error accessing {url}: {e}")
            return False, None

    def check_common_wp_files(self, url):
        common_files = ['readme.html', 'wp-links-opml.php', 'license.txt']
        for file in common_files:
            try:
                response = requests.get(f"{url}/{file}", timeout=10)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                continue
        return False

    def check_wp_rest_api(self, url):
        try:
            response = requests.get(f"{url}/wp-json/", timeout=10)
            if response.status_code == 200 and 'application/json' in response.headers.get('Content-Type', ''):
                return True
        except requests.RequestException:
            pass
        return False


class ScraperApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.show_disclaimer()

    def initUI(self):
        self.setWindowTitle('Wordpress Scraper By FRENZY')
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        # Keyword file input
        hbox = QHBoxLayout()
        self.keyword_file_input = QLineEdit(self)
        self.keyword_file_input.setPlaceholderText('Select keyword file...')
        self.keyword_file_btn = QPushButton('Browse', self)
        self.keyword_file_btn.clicked.connect(self.browse_keyword_file)
        hbox.addWidget(self.keyword_file_input)
        hbox.addWidget(self.keyword_file_btn)
        layout.addLayout(hbox)

        # Number of pages input
        hbox = QHBoxLayout()
        self.num_pages_input = QLineEdit(self)
        self.num_pages_input.setPlaceholderText('Number of pages to scrape (default 9)')
        hbox.addWidget(QLabel('Number of Pages:', self))
        hbox.addWidget(self.num_pages_input)
        layout.addLayout(hbox)

        # Domain output file input
        hbox = QHBoxLayout()
        self.domain_output_file_input = QLineEdit(self)
        self.domain_output_file_input.setPlaceholderText('Select output TXT file for domains...')
        self.domain_output_file_btn = QPushButton('Browse', self)
        self.domain_output_file_btn.clicked.connect(self.browse_domain_output_file)
        hbox.addWidget(self.domain_output_file_input)
        hbox.addWidget(self.domain_output_file_btn)
        layout.addLayout(hbox)

        # WP output file input
        hbox = QHBoxLayout()
        self.wp_output_file_input = QLineEdit(self)
        self.wp_output_file_input.setPlaceholderText('Select output CSV file for WP versions...')
        self.wp_output_file_btn = QPushButton('Browse', self)
        self.wp_output_file_btn.clicked.connect(self.browse_wp_output_file)
        hbox.addWidget(self.wp_output_file_input)
        hbox.addWidget(self.wp_output_file_btn)
        layout.addLayout(hbox)

        # Radio buttons for append or create new CSV
        self.append_new_group = QButtonGroup(self)
        self.append_radio = QRadioButton("Append to existing CSV")
        self.new_radio = QRadioButton("Create new CSV")
        self.append_radio.setChecked(True)
        self.append_new_group.addButton(self.append_radio)
        self.append_new_group.addButton(self.new_radio)
        layout.addWidget(self.append_radio)
        layout.addWidget(self.new_radio)

        # Progress display
        self.progress_display = QTextEdit(self)
        self.progress_display.setReadOnly(True)
        layout.addWidget(self.progress_display)

        # Start button
        self.start_btn = QPushButton('Start', self)
        self.start_btn.clicked.connect(self.start_scraping)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)

    def browse_keyword_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Keyword File", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_name:
            self.keyword_file_input.setText(file_name)

    def browse_domain_output_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Select Output File for Domains", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_name:
            self.domain_output_file_input.setText(file_name)

    def browse_wp_output_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Select Output File for WP Versions", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_name:
            self.wp_output_file_input.setText(file_name)

    def start_scraping(self):
        keyword_file = self.keyword_file_input.text()
        num_pages = self.num_pages_input.text()
        domain_output_file = self.domain_output_file_input.text()
        wp_output_file = self.wp_output_file_input.text()
        append_to_existing = self.append_radio.isChecked()

        if not keyword_file or not domain_output_file or not wp_output_file:
            QMessageBox.warning(self, 'Input Error', 'Please provide all required inputs.')
            return

        try:
            with open(keyword_file, 'r', encoding='utf-8') as file:
                keywords = [line.strip() for line in file.readlines()]
        except Exception as e:
            QMessageBox.critical(self, 'File Error', f'Error reading keyword file: {e}')
            return

        if not num_pages.isdigit():
            num_pages = '9'
        num_pages = int(num_pages)

        self.scrape_worker = ScrapeWorker(keywords, num_pages, domain_output_file)
        self.scrape_worker.progress.connect(self.update_progress)
        self.scrape_worker.finished_domains.connect(lambda domains: self.start_wp_scan(domains, wp_output_file, append_to_existing))
        self.scrape_worker.start()

    def start_wp_scan(self, domains, wp_output_file, append_to_existing):
        self.wp_scan_worker = WPScanWorker(domains, wp_output_file)
        self.wp_scan_worker.progress.connect(self.update_progress)
        self.wp_scan_worker.finished.connect(lambda wp_sites: self.save_wp_versions(wp_sites, wp_output_file, append_to_existing))
        self.wp_scan_worker.start()

    def save_wp_versions(self, wp_sites, wp_output_file, append_to_existing):
        if append_to_existing and os.path.exists(wp_output_file):
            mode = 'a'
            existing_sites = set()
            try:
                with open(wp_output_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        existing_sites.add(row['site'])
            except Exception as e:
                self.update_progress(f"Error reading existing CSV file: {e}")
        else:
            mode = 'w'
            existing_sites = set()

        try:
            with open(wp_output_file, mode, newline='', encoding='utf-8') as file:
                fieldnames = ['site', 'version']
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if mode == 'w':
                    writer.writeheader()
                for site in wp_sites:
                    if site['site'] not in existing_sites:
                        writer.writerow(site)
            self.update_progress(f"WordPress versions saved to {wp_output_file}")
        except Exception as e:
            self.update_progress(f"Error writing to CSV file: {e}")

    def update_progress(self, message):
        self.progress_display.append(message)
        self.progress_display.ensureCursorVisible()

    def show_disclaimer(self):
        disclaimer = (
            "Disclaimer: This tool is for educational purposes only. "
            "Ensure you have proper authorization before scanning any websites. "
            "Unauthorized scanning is illegal and unethical."
        )
        QMessageBox.information(self, 'Disclaimer', disclaimer)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ScraperApp()
    ex.show()
    sys.exit(app.exec_())
