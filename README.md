# WPSCRAPER-GUI
WordPress Scraper by FRENZY is a Python-based tool with a PyQt5 GUI for scraping domains from Google based on specified keywords and checking if they use WordPress, including detecting the version. Ideal for SEO research and competitive analysis, this tool provides an easy way to gather and analyze WordPress sites.
# WordPress Scraper by FRENZY

**WordPress Scraper by FRENZY** is a powerful and user-friendly tool designed for scraping domains from Google search results and checking their WordPress version. Built using Python and PyQt5, this tool allows users to automate the process of finding websites based on keywords and determining if they are using WordPress, including the version number.

## Features

- **Keyword-Based Domain Scraping**: Scrape domains based on a list of keywords by specifying the number of search result pages to process.
- **WordPress Detection**: Identify whether a domain is running WordPress and retrieve the version if available.
- **Output Options**: Save domains to a text file and WordPress version information to a CSV file, with options to append to an existing CSV or create a new one.
- **User-Friendly Interface**: A graphical user interface (GUI) built with PyQt5 for easy interaction and progress tracking.

## Requirements

- Python 3.x
- PyQt5
- BeautifulSoup
- Requests

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/wordpress-scraper.git
    ```

2. Navigate to the project directory:

    ```bash
    cd wordpress-scraper
    ```

3. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Run the application:

    ```bash
    python main.py
    ```

2. **Keyword File**: Upload a text file containing the keywords you want to search.

3. **Number of Pages**: Specify the number of pages of search results to scrape.

4. **Domain Output File**: Choose a location to save the scraped domains.

5. **WP Output File**: Choose a location to save the WordPress version information in CSV format.

6. **Start**: Click the 'Start' button to begin the scraping and checking process.

## Disclaimer

This tool is for educational purposes only. Ensure you have proper authorization before scanning any websites. Unauthorized scanning is illegal and unethical.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have suggestions or improvements.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
