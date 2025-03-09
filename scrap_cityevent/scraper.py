"""
Module for scraping a website to find events with specified search terms.
"""
import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
import re
import hashlib
import unicodedata

logger = logging.getLogger(__name__)

class EventScraper:
    def __init__(self, url: str, data_file: str = "scrap_cityevent/data/events.json", max_pages: int = 5, 
                 search_terms: Union[str, List[str]] = None, debug: bool = False,
                 exact_matching: bool = True, 
                 variants_file: Optional[str] = None,
                 term_variants: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the scraper with the target URL and data file for storing processed events.
        
        Args:
            url: The URL of the webpage to scrape
            data_file: Path to the JSON file to store processed events
            max_pages: Maximum number of pages to scrape (to prevent infinite loops)
            search_terms: Term or list of terms to search for in events
            debug: Enable debug mode for more verbose logging
            exact_matching: If True, only match events that exactly contain the search terms
            variants_file: Path to a JSON file containing term variants
            term_variants: Dictionary mapping search terms to their variants
        """
        self.url = url
        self.data_file = data_file
        self.max_pages = max_pages
        self.exact_matching = exact_matching
        self.debug = debug
        
        # Initialize search_terms first (to avoid the 'has no attribute' error)
        self.search_terms = self._normalize_search_terms(search_terms)
        
        # Then load term variants
        self.term_variants = term_variants or self._load_term_variants(variants_file)
        
        # Special handling for variants if in search terms
        self._add_term_variants()
            
        if debug:
            logger.debug(f"Initialized scraper with search terms: {self.search_terms}")
            logger.debug(f"Term variants loaded: {self.term_variants}")
        
        # Set up directory for data file if it doesn't exist
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        # Load processed events from file
        self.processed_events = self._load_processed_events()
        
        if debug:
            logger.debug(f"Initialized scraper with URL: {url}")
            logger.debug(f"Search terms: {self.search_terms}")
            logger.debug(f"Exact matching: {exact_matching}")
    
    def _load_term_variants(self, variants_file: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Load term variants from a file or environment variables.
        
        Args:
            variants_file: Path to a JSON file with term variants
            
        Returns:
            Dictionary mapping terms to their variants
        """
        variants = {}
        
        # First, try to load from a file if provided
        if variants_file and os.path.exists(variants_file):
            try:
                with open(variants_file, 'r', encoding='utf-8') as f:
                    variants = json.load(f)
                logger.info(f"Loaded term variants from {variants_file}: {list(variants.keys())}")
                
                # Special case: if variants.json contains only one key and 
                # that key doesn't match a search term directly, 
                # assume it contains the variants for the primary term
                if len(variants) == 1 and len(self.search_terms) == 1:
                    json_key = list(variants.keys())[0]
                    search_term = self.search_terms[0]
                    
                    # If key is not the same as search term, remap it
                    if json_key != search_term and json_key not in self.search_terms:
                        logger.info(f"Remapping variants from '{json_key}' to '{search_term}'")
                        variants[search_term] = variants[json_key]
                
            except Exception as e:
                logger.error(f"Error loading term variants from {variants_file}: {e}")
        
        # Then, try to load from environment variables using JSON
        env_variants = os.environ.get('TERM_VARIANTS', '').strip()
        if env_variants:
            try:
                # Try to parse as JSON
                env_var_dict = json.loads(env_variants)
                variants.update(env_var_dict)
                logger.info("Loaded term variants from TERM_VARIANTS environment variable")
            except json.JSONDecodeError:
                logger.warning("TERM_VARIANTS is not valid JSON, skipping")
        
        # Also check for primary term and its variants
        primary_term = os.environ.get('PRIMARY_TERM', '')
        if primary_term:
            primary_variants = os.environ.get('PRIMARY_TERM_VARIANTS', '')
            if primary_variants:
                variants[primary_term] = [v.strip() for v in primary_variants.split(',') if v.strip()]
                logger.info(f"Loaded primary term variants from environment: {len(variants[primary_term])} variants")
        
        return variants
    
    def _add_term_variants(self):
        """Add variants for search terms based on the loaded term variants."""
        # Create a copy to avoid modifying during iteration
        original_terms = list(self.search_terms)
        variants_added = 0
        
        # If we have variants but no original search terms, add all variants
        if self.term_variants and not original_terms:
            logger.info("No search terms but variants found - adding all variants")
            for key, variants in self.term_variants.items():
                for variant in variants:
                    if variant.strip() and variant not in self.search_terms:
                        self.search_terms.append(variant)
                        variants_added += 1
            # Also add the key itself as a search term
            for key in self.term_variants.keys():
                if key not in self.search_terms:
                    self.search_terms.append(key)
                    variants_added += 1
            return
                    
        # For each original term, add all variants that might match
        for term in original_terms:
            normalized_term = self._normalize_text(term)
            
            # Special handling: If we have a variants file but no exact key match,
            # just add ALL variants from ALL keys if any key contains any part of the search term
            if len(self.term_variants) > 0 and term not in self.term_variants:
                # Find any key that contains part of our search term or vice versa
                for key, variants in self.term_variants.items():
                    key_lower = key.lower()
                    term_lower = term.lower()
                    key_normalized = self._normalize_text(key)
                    
                    if (key_lower in term_lower or 
                        term_lower in key_lower or
                        any(v.lower() in term_lower for v in variants) or
                        any(term_lower in v.lower() for v in variants)):
                        
                        # Add all variants for this key
                        normalized_terms = [t.lower() for t in self.search_terms]
                        for variant in variants:
                            if variant.lower() not in normalized_terms:
                                self.search_terms.append(variant)
                                variants_added += 1
            else:
                # Normal exact matching approach
                for key, variants in self.term_variants.items():
                    key_normalized = self._normalize_text(key)
                    if (term.lower() == key.lower() or 
                        normalized_term == key_normalized or
                        term.lower() in key.lower() or 
                        key.lower() in term.lower()):
                        
                        # Add all variants that aren't already in the search terms
                        normalized_terms = [t.lower() for t in self.search_terms]
                        for variant in variants:
                            if variant.lower() not in normalized_terms:
                                self.search_terms.append(variant)
                                variants_added += 1
        
        if variants_added > 0:
            logger.info(f"Added {variants_added} term variants: total terms = {len(self.search_terms)}")
        else:
            logger.warning(f"No variants added for search terms: {self.search_terms}. Available keys: {list(self.term_variants.keys())}")
    
    def _normalize_search_terms(self, search_terms: Union[str, List[str]]) -> List[str]:
        """
        Normalize search terms for consistent matching.
        
        Args:
            search_terms: Term or list of terms to normalize
            
        Returns:
            List of normalized search terms
        """
        if not search_terms:
            return []
            
        # Convert to list if string
        if isinstance(search_terms, str):
            search_terms = [search_terms]
            
        # Normalize each term
        normalized_terms = []
        for term in search_terms:
            # Original term (preserve for matching)
            normalized_terms.append(term)
            
            # Also normalize accents for better matching
            normalized = self._normalize_text(term)
            if normalized and normalized != term.lower() and normalized not in normalized_terms:
                normalized_terms.append(normalized)
                
        return normalized_terms
        
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text by converting to lowercase and removing diacritics.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
            
        # Convert to lowercase
        text = text.lower()
        
        # Remove diacritics
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        
        return text
        
    def _load_processed_events(self) -> Dict[str, Dict[str, Any]]:
        """
        Load processed events from the data file.
        
        Returns:
            Dictionary of processed events with event IDs as keys
        """
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading processed events: {e}")
                return {}
        return {}
        
    def _save_processed_events(self) -> None:
        """Save processed events to the data file."""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving processed events: {e}")
            
    def _generate_event_id(self, event: Dict[str, Any]) -> str:
        """
        Generate a unique ID for an event based on its title, date, and URL.
        
        Args:
            event: Event dictionary with title, date, and link fields
            
        Returns:
            Unique ID for the event
        """
        # Create a string with key event details
        event_str = f"{event.get('title', '')}-{event.get('date', '')}-{event.get('link', '')}"
        
        # Generate a hash of the string
        return hashlib.md5(event_str.encode('utf-8')).hexdigest()
        
    def _extract_date(self, event_content: str) -> str:
        """
        Extract date information from event content.
        
        Args:
            event_content: HTML content of the event
            
        Returns:
            Extracted date if found, empty string otherwise
        """
        # Clean the content
        content = event_content.replace('&nbsp;', ' ').strip()
        content_lower = content.lower()
        
        # First, look for day-of-week patterns which are most reliable
        day_patterns = [
            # Day of week + date patterns (highly reliable)
            r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b',
            r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\b',
            r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}/\d{1,2}\b',
        ]
        
        for pattern in day_patterns:
            matches = re.search(pattern, content_lower, re.IGNORECASE)
            if matches:
                return matches.group(0).capitalize()  # Return capitalized version
        
        # Second, look for typical date patterns
        date_patterns = [
            # Clean date formats with month names
            r'\b\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)(?:\s+\d{2,4})?\b',
            r'\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)(?:\s+\d{2,4})?\b',
            # Date phrases
            r'du\s+\d{1,2}\s+au\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)',
            r'le\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)',
            # Date formats with month names first
            r'\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{1,2}(?:,?\s+\d{2,4})?\b',
            r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,?\s+\d{2,4})?\b',
        ]
        
        for pattern in date_patterns:
            matches = re.search(pattern, content_lower, re.IGNORECASE)
            if matches:
                return matches.group(0).capitalize()
                
        # Third, try numeric date formats but validate they're likely real dates
        numeric_patterns = [
            r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b',  # DD/MM/YYYY or MM/DD/YYYY
            r'\b\d{1,2}[-]\d{1,2}[-]\d{2,4}\b',    # DD-MM-YYYY
        ]
        
        for pattern in numeric_patterns:
            matches = re.search(pattern, content, re.IGNORECASE)
            if matches:
                date_str = matches.group(0)
                # Validate it looks like a real date (not phone numbers or other numeric patterns)
                parts = re.split(r'[./-]', date_str)
                if len(parts) == 3:
                    # Check if components are valid date parts
                    if (1 <= int(parts[0]) <= 31 and 1 <= int(parts[1]) <= 12) or \
                       (1 <= int(parts[1]) <= 31 and 1 <= int(parts[0]) <= 12):
                        return date_str
                elif len(parts) == 2:
                    # For DD/MM format, check if values are in valid ranges
                    if (1 <= int(parts[0]) <= 31 and 1 <= int(parts[1]) <= 12) or \
                       (1 <= int(parts[1]) <= 31 and 1 <= int(parts[0]) <= 12):
                        return date_str
        
        # Last resort: if no specific pattern matched, look for any combination of day/month
        # Try to find standalone month names with nearby numbers
        month_pattern = r'\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|january|february|march|april|may|june|july|august|september|october|november|december)\b'
        month_matches = re.search(month_pattern, content_lower, re.IGNORECASE)
        
        if month_matches:
            # Found a month name, look for nearby numbers
            month = month_matches.group(0)
            month_idx = content_lower.find(month.lower())
            
            # Look for numbers within 20 chars before or after the month
            context_start = max(0, month_idx - 20)
            context_end = min(len(content), month_idx + len(month) + 20)
            context = content[context_start:context_end]
            
            # Find all numbers in the context
            numbers = re.findall(r'\b\d{1,2}\b', context)
            if numbers:
                # Find the number closest to the month
                for number in numbers:
                    if 1 <= int(number) <= 31:  # Valid day of month
                        # Create a properly formatted date string
                        if month_idx < content_lower.find(number, context_start, context_end):
                            return f"{month.capitalize()} {number}"  # Month first
                        else:
                            return f"{number} {month.capitalize()}"  # Day first
            
            # If no valid day number found, just return the month
            return month.capitalize()
            
        # If no date pattern found at all, return empty string
        return ""
        
    def _process_event(self, event_html: str) -> Optional[Dict[str, Any]]:
        """
        Process an event HTML element and extract event details.
        
        Args:
            event_html: HTML element containing event information
            
        Returns:
            Dictionary with event details or None if no match with search terms
        """
        try:
            soup = BeautifulSoup(event_html, 'html.parser')
            
            # Check if this is a div.event element (my website specific)
            is_website_event = 'class="event"' in event_html
            
            # Extract event title - try different potential elements
            title_elem = None
            
            if is_website_event:
                # For website.com, the title is typically in the h2
                title_elem = soup.find('h2')
                if not title_elem:
                    # Sometimes title might be in a strong tag
                    title_elem = soup.find('strong')
                    
                # If still no title element, look for the first significant text
                if not title_elem:
                    for elem in soup.find_all(['div', 'p', 'span']):
                        if len(elem.text.strip()) > 10:  # At least 10 chars
                            title_elem = elem
                            break
            else:
                # For other sites, try standard approaches
                title_elem = soup.find('h2')
                if not title_elem:
                    title_elem = soup.find('h3') or soup.find('h4') or soup.find('.event-title') or soup.find('strong')
                    
                # If still no title element, try using the first paragraph or div with text
                if not title_elem:
                    for elem in soup.find_all(['p', 'div', 'span']):
                        if elem.text.strip():
                            title_elem = elem
                            break
                        
            if not title_elem:
                # If we can't find a title, use the first text content
                title = soup.get_text().strip().split('\n')[0][:100]  # First line, truncated
            else:
                title = title_elem.text.strip()
                
            if not title:
                # No title found, can't process this event
                return None
            
            # Extract link - try different approaches
            link = "#"  # Default value
            
            # For website, the link is typically in the parent container
            if is_website_event:
                parent_link = soup.find_all('a', href=True)
                if parent_link:
                    link = parent_link[0]['href']
            else:
                link_elem = soup.find('a')
                if link_elem and 'href' in link_elem.attrs:
                    link = link_elem['href']
                else:
                    # Try to find any link in the element
                    links = soup.find_all('a')
                    link = links[0]['href'] if links and 'href' in links[0].attrs else "#"
            
            # Make sure link is absolute
            if link.startswith('/'):
                base_url = self.url
                if base_url.endswith('/'):
                    base_url = base_url[:-1]
                link = base_url + link
            
            # Extract event info - save the full text content
            # For website, the full text is the important part
            full_text = soup.get_text().strip()
            info = full_text
            
            # If the title is included in the info, remove it to avoid duplication
            if title in info:
                info = info.replace(title, '', 1).strip()
                
            # Remove excess whitespace and normalize linebreaks
            info = re.sub(r'\s+', ' ', info).strip()
            info = info.replace('. ', '.\n').replace('! ', '!\n').replace('? ', '?\n')
            
            # If info is too long, truncate it
            if len(info) > 2000:
                info = info[:2000] + "..."
                
            # Extract date
            date = self._extract_date(event_html)
            
            # Validate the date - make sure it's not just random numbers
            if date and re.match(r'^[\d.]+$', date):
                # If it's just numbers with periods (like "04.68.29"), it's probably not a date
                # Try to extract a better date from the event text
                # Look for month names
                month_pattern = r'\b(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b'
                month_match = re.search(month_pattern, full_text.lower(), re.IGNORECASE)
                
                if month_match:
                    # Found a month name, try to extract a proper date
                    month_context = full_text[max(0, month_match.start() - 20):min(len(full_text), month_match.end() + 20)]
                    proper_date = self._extract_date(month_context)
                    if proper_date:
                        date = proper_date
                        logger.debug(f"Replaced numeric date with proper date: {date}")
                    else:
                        # If no proper date could be extracted, just use the month
                        date = month_match.group(0).capitalize()
                else:
                    # If no month name found, check for day-of-week names
                    day_pattern = r'\b(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b'
                    day_match = re.search(day_pattern, full_text.lower(), re.IGNORECASE)
                    if day_match:
                        # Extract context around day name
                        day_context = full_text[max(0, day_match.start() - 10):min(len(full_text), day_match.end() + 30)]
                        date = day_context.strip()
                        logger.debug(f"Using day-of-week context: {date}")
            
            # Check if this event matches our search terms
            normalized_title = self._normalize_text(title)
            normalized_info = self._normalize_text(info)
            
            matching_terms = []
            
            # Check for matches in title and info
            for term in self.search_terms:
                term_lower = term.lower()
                term_normalized = self._normalize_text(term)
                
                # Exact matching mode
                if self.exact_matching:
                    # Check for exact matches
                    if term_lower in normalized_title or term_lower in normalized_info or \
                       term_normalized in normalized_title or term_normalized in normalized_info:
                        if term not in matching_terms:
                            matching_terms.append(term)
                else:
                    # Check for partial matches
                    if term_lower in normalized_title or term_lower in normalized_info or \
                       term_normalized in normalized_title or term_normalized in normalized_info:
                        if term not in matching_terms:
                            matching_terms.append(term)
            
            # Skip if no matching terms found
            if not matching_terms:
                return None
                
            # Create the event dict with matching terms for reference
            event = {
                'title': matching_terms[0] if matching_terms else title,  # Use the matching term as title
                'original_title': title,  # Keep the original title for reference
                'link': link,
                'info': info,
                'date': date,
                'found_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'matching_terms': matching_terms
            }
            
            # Generate a unique ID for this event
            event['id'] = self._generate_event_id(event)
            
            if self.debug:
                logger.debug(f"Found matching event: {title} (ID: {event['id']})")
                logger.debug(f"  Date: {date}")
                logger.debug(f"  Matching terms: {matching_terms}")
                
            return event
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None
            
    def find_new_events(self) -> List[Dict[str, Any]]:
        """
        Scrape the website and find new events matching the search terms.
        
        Returns:
            List of dictionaries with event information
        """
        new_events = []
        event_count = 0
        
        # Make sure we have search terms or variants
        if not self.search_terms and not self.term_variants:
            logger.error("No search terms or variants provided. Cannot find events.")
            return []
            
        # Add variants from any generic variants file if there are no search terms
        if not self.search_terms and self.term_variants:
            for key, variants in self.term_variants.items():
                self.search_terms.extend(variants)
                if key not in self.search_terms:
                    self.search_terms.append(key)
            logger.info(f"Added {len(self.search_terms)} search terms from variants")
        
        if self.debug:
            logger.debug(f"Using search terms: {self.search_terms}")
        
        try:
            current_url = self.url
            pages_scraped = 0
            
            while current_url and pages_scraped < self.max_pages:
                logger.info(f"Scraping page: {current_url}")
                
                # Fetch the page
                response = requests.get(current_url, timeout=30)
                response.raise_for_status()
                
                # Parse HTML content
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Try to find event elements with different selectors
                event_elements = []
                
                # Try with standard article tag first
                articles = soup.find_all('article')
                if articles:
                    logger.info(f"Found {len(articles)} event elements with 'article' tag")
                    event_elements = articles
                else:
                    # Try alternative selectors
                    for selector in ['div.event', '.event-item', 'div.ce_text', '.post', '.item', '.newsBox', '.event-box']:
                        elements = soup.select(selector)
                        if elements:
                            logger.info(f"Found {len(elements)} event elements with selector '{selector}'")
                            event_elements = elements
                            break
                            
                    # If still no elements, try looking for divs with text content
                    if not event_elements:
                        logger.info("No standard event elements found, trying to find text-rich divs")
                        for div in soup.find_all('div'):
                            text = div.get_text().strip()
                            if len(text) > 100:  # Substantial text content
                                event_elements.append(div)
                        
                        if event_elements:
                            logger.info(f"Found {len(event_elements)} potential event elements with text content")
                
                # Process each event
                for event_elem in event_elements:
                    event = self._process_event(str(event_elem))
                    
                    if event:
                        event_count += 1
                        event_id = event['id']
                        
                        # Check if we've already processed this event
                        if event_id not in self.processed_events:
                            new_events.append(event)
                            self.processed_events[event_id] = {
                                'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'notified': False
                            }
                            
                # Find link to next page
                next_page = None
                pagination = soup.find('ul', class_='pagination')
                if pagination:
                    next_link = pagination.find('a', rel='next')
                    if next_link and 'href' in next_link.attrs:
                        next_href = next_link['href']
                        # Make sure URL is absolute
                        if next_href.startswith('/'):
                            base_url = self.url
                            if '?' in base_url:
                                base_url = base_url.split('?')[0]
                            if base_url.endswith('/'):
                                base_url = base_url[:-1]
                            next_href = base_url + next_href
                        next_page = next_href
                
                # Move to next page or break the loop
                if next_page:
                    current_url = next_page
                else:
                    break
                    
                pages_scraped += 1
                
            # Save processed events
            self._save_processed_events()
            
            logger.info(f"Scraped {pages_scraped + 1} pages, found {event_count} events, {len(new_events)} new events.")
            return new_events
            
        except Exception as e:
            logger.exception(f"Error finding events: {e}")
            return []
            
    def mark_as_notified(self, event_id: str) -> None:
        """
        Mark an event as notified.
        
        Args:
            event_id: ID of the event to mark
        """
        if event_id in self.processed_events:
            self.processed_events[event_id]['notified'] = True
            self.processed_events[event_id]['notified_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._save_processed_events() 