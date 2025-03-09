# Changes and Improvements

## Latest Updates

### 2023-07-01: Major Refactoring and Enhanced Modularity

- **General Improvements**:
  - Transformed the tool into a fully modular event scraper that works with any type of event
  - Maintained special handling for "TERMS" while allowing full modularity
  - Improved code organization, documentation, and type hinting
  - Enhanced error handling throughout the codebase
  - Added better logging with more informative messages

- **Event Scraper Enhancements**:
  - Rewrote the search algorithm to be more flexible and work with any search terms
  - Added automatic variant detection for writing workshops ("Atelier d'écriture")
  - Improved date extraction with more comprehensive patterns for multiple languages
  - Enhanced event detection with better HTML parsing
  - Added support for matching terms display in notifications
  - Implemented more robust HTML parsing with better error recovery

- **Email System Improvements**:
  - Redesigned all email templates with professional HTML styling
  - Updated the email registration system to be dynamic for any event type
  - Added conditional formatting for phone numbers and other optional fields
  - Improved HTML email formatting with better structure and readability
  - Enhanced error handling for email authentication issues

- **Command Line Interface**:
  - Updated CLI arguments to be more intuitive and better documented
  - Added `--default-term` option for using fallback search terms
  - Added better validation for required parameters
  - Made error messages more informative for missing configuration

- **Configuration**:
  - Added a comprehensive `.env.example` file with detailed comments
  - Added DEFAULT_TERM environment variable for setting default search terms
  - Improved environment variable handling with better defaults
  - Added support for fully configurable search terms

## How to Use

1. Clone the repository
2. Copy `.env.example` to `.env` and fill in your configuration:
   ```
   cp .env.example .env
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the scraper:
   ```
   python -m scrap_cityevent.main
   ```

### Command Line Options

```
python -m scrap_cityevent.main --help
```

Important options:
- `--search-terms "term1,term2,term3"` - Specify search terms
- `--default-term "Atelier d'écriture"` - Default term to use if no search terms provided
- `--url URL` - URL to scrape
- `--sender-email EMAIL` - Email to send from
- `--receiver-email EMAIL` - Email to send to
- `--city-email EMAIL` - Email for event registrations
- `--name NAME` - Your name for email signatures
- `--exact` - Use exact matching for search terms
- `--reset` - Reset the database of processed events 