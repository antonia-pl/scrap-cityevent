# Event Notifier

A flexible web scraping tool that continuously monitors website pages for cities featuring upcoming events, filtering results by specific search terms to send targeted email notifications.

## Features

- Scrapes websites for events matching configurable search terms
- Handles pagination to navigate through multiple pages of events
- Sends professionally styled HTML email notifications for new events
- Includes a signup button in notifications for easy event registration
- Avoids duplicate notifications for the same event
- Robust date extraction for events in multiple formats and languages
- Special handling for "Word" events with variant detection
- Command-line interface with extensive configuration options
- Environment variable support for easy configuration
- Built with Poetry for dependency management

## Installation

1. Make sure you have Python 3.10+ and Poetry installed
2. Clone this repository
3. Install dependencies with Poetry:

```bash
poetry install
```

## Configuration

1. Create the `.env` file

2. Edit the `.env` file with your settings:
   - `SCRAPER_URL`: The URL of the webpage to scrape
   - `SEARCH_TERMS`: Comma-separated list of terms to search for in events
   - `DEFAULT_TERM`: Default term to use if no search terms are provided (exemple: "Garuda")
   - `SENDER_EMAIL`: Your email address (to send notifications from)
   - `EMAIL_PASSWORD`: Your email password or app password for Gmail
   - `RECEIVER_EMAIL`: Email address to receive notifications
   - `CITY_EMAIL`: Email address for event registrations
   - `NAME`: Your name for email signatures
   - `PHONE`: Your phone number for contact information

### Note for Gmail users

If using Gmail, you'll need to create an "App Password" for less secure apps:

1. Go to your Google Account > Security
2. Under "Signing in to Google", select "App passwords"
3. Generate a new app password and use it in the `.env` file

## Usage

Run the script with Poetry:

```bash
poetry run python -m scrap_cityevent.main
```

Or, if you have activated the Poetry virtual environment:

```bash
python -m scrap_cityevent.main
```

### Command-line Arguments

You can also provide configuration via command-line arguments:

```bash
python -m scrap_cityevent.main --url https://example.com/events --search-terms "term1,term2,term3" --sender-email your-sender-notification.email@gmail.com --receiver-email receive-notification.email@gmail.com
```

Run with `--help` to see all options:

```bash
python -m scrap_cityevent.main --help
```

### Key Command-line Options

- `--search-terms "term1,term2,term3"` - Specify search terms (comma-separated)
- `--default-term "Atelier d'écriture"` - Default term to use if no search terms provided
- `--url URL` - URL to scrape
- `--sender-email EMAIL` - Email to send from
- `--receiver-email EMAIL` - Email to send to
- `--city-email EMAIL` - Email for event registrations
- `--name NAME` - Your name for email signatures
- `--phone PHONE` - Your phone number for contact information
- `--exact` - Use exact matching for search terms (default: True)
- `--reset` - Reset the database of processed events
- `--debug` - Enable debug mode for more verbose logging

## Scheduling Regular Runs

To check for new events regularly, you can set up a cron job:

```bash
# Run every hour
0 * * * * cd /path/to/event-notifier && /path/to/poetry run python -m scrap_cityevent.main
```

## Customizing the Scraper

The scraper is designed to work with a variety of website structures. The default configuration works well with sites that use standard HTML structures for events, typically with:

- Events contained in `<article>` elements
- Event titles in `<h2>` elements
- Event descriptions in `<p>` elements
- Links to event details in `<a>` elements
- Pagination with "next" links

If your target website has a different structure, you may need to customize the `_process_event` method in `scrap_cityevent/scraper.py`.
