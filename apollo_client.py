"""
Apollo.io API client with caching support.
Handles People Search, Contact Creation, and Sequence Enrollment.
"""
import requests
from typing import Optional
import logging

from config import config
from schema import ApolloContact
from storage import get_cached_contacts, cache_contacts

logger = logging.getLogger(__name__)

APOLLO_BASE_URL = "https://api.apollo.io/v1"


class ApolloClient:
    """Client for Apollo.io API operations."""

    def __init__(self):
        self.api_key = config.APOLLO_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }

    def _make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make an authenticated request to Apollo API."""
        url = f"{APOLLO_BASE_URL}/{endpoint}"

        # Apollo uses api_key in the request body, not headers
        payload = data or {}
        payload["api_key"] = self.api_key

        response = requests.request(
            method=method,
            url=url,
            json=payload,
            headers=self.headers,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Apollo API error: {response.status_code} - {response.text}")
            response.raise_for_status()

        return response.json()

    def search_people(
        self,
        domain: str,
        titles: list[str] = None,
        use_cache: bool = True
    ) -> list[ApolloContact]:
        """
        Search for contacts at a company by domain.

        Args:
            domain: Company domain (e.g., "shopify.com")
            titles: List of job titles to filter by (default: localization-related)
            use_cache: Whether to use cached results

        Returns:
            List of ApolloContact objects
        """
        # Check cache first
        if use_cache:
            cached = get_cached_contacts(domain)
            if cached:
                logger.info(f"Cache hit for domain: {domain}")
                return [ApolloContact(**c) for c in cached]

        # Default titles for localization decision makers
        if titles is None:
            titles = [
                "localization",
                "internationalization",
                "i18n",
                "translation",
                "globalization",
                "product",
                "engineering",
                "VP Engineering",
                "Head of Product",
                "CTO",
                "Director of Engineering"
            ]

        logger.info(f"Searching Apollo for contacts at: {domain}")

        data = {
            "q_organization_domains": domain,
            "person_titles": titles,
            "page": 1,
            "per_page": 10
        }

        result = self._make_request("POST", "mixed_people/search", data)

        contacts = []
        for person in result.get("people", []):
            contact = ApolloContact(
                id=person.get("id", ""),
                first_name=person.get("first_name"),
                last_name=person.get("last_name"),
                name=person.get("name"),
                title=person.get("title"),
                email=person.get("email"),
                linkedin_url=person.get("linkedin_url"),
                organization_name=person.get("organization", {}).get("name")
            )
            contacts.append(contact)

        # Cache the results
        if contacts:
            cache_contacts(domain, [c.model_dump() for c in contacts])

        return contacts

    def create_contact(
        self,
        email: str,
        first_name: str,
        last_name: str,
        organization_name: str,
        title: Optional[str] = None,
        custom_fields: dict = None
    ) -> dict:
        """
        Create a contact in Apollo with custom fields.

        Args:
            email: Contact email
            first_name: Contact first name
            last_name: Contact last name
            organization_name: Company name
            title: Job title
            custom_fields: Dict of custom field values (personalized_subject, personalized_email_1, i18n_signals)

        Returns:
            Apollo API response with created contact
        """
        data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "organization_name": organization_name,
        }

        if title:
            data["title"] = title

        # Add custom fields using typed_custom_fields
        if custom_fields:
            data["typed_custom_fields"] = custom_fields

        logger.info(f"Creating contact in Apollo: {email}")
        return self._make_request("POST", "contacts", data)

    def add_to_sequence(self, contact_id: str, sequence_id: str = None) -> dict:
        """
        Add a contact to a sequence.

        Args:
            contact_id: Apollo contact ID
            sequence_id: Sequence ID (defaults to configured APOLLO_SEQUENCE_ID)

        Returns:
            Apollo API response
        """
        seq_id = sequence_id or config.APOLLO_SEQUENCE_ID

        data = {
            "contact_ids": [contact_id],
            "emailer_campaign_id": seq_id
        }

        logger.info(f"Adding contact {contact_id} to sequence {seq_id}")
        return self._make_request("POST", "emailer_campaigns/add_contact_ids", data)

    def get_contact(self, contact_id: str) -> Optional[ApolloContact]:
        """Get a contact by ID."""
        try:
            result = self._make_request("GET", f"contacts/{contact_id}", {})
            contact_data = result.get("contact", {})
            return ApolloContact(**contact_data)
        except Exception as e:
            logger.error(f"Failed to get contact {contact_id}: {e}")
            return None


# Singleton instance
apollo_client = ApolloClient()
