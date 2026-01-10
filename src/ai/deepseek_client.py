"""DeepSeek API client for AI decision-making."""

import json
from typing import Any, Dict, Optional

import requests

from ..utils.config import config


class DeepSeekClient:
    """Client for interacting with DeepSeek API."""

    def __init__(self):
        self.api_key = config.get("ai.api_key")
        self.model = config.get("ai.model", "deepseek-chat")
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.max_tokens = config.get("ai.max_tokens", 500)
        self.temperature = config.get("ai.temperature", 0.7)
        self.timeout = config.get("ai.timeout_seconds", 30)
        self.top_p = config.get("ai.top_p", None)
        self.frequency_penalty = config.get("ai.frequency_penalty", None)
        self.presence_penalty = config.get("ai.presence_penalty", None)

    def make_decision(
        self, system_prompt: str, user_prompt: str
    ) -> Optional[Dict[str, Any]]:
        """
        Send a decision request to DeepSeek and get structured response.

        Returns the parsed JSON response or None if failed.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        # Add optional parameters if configured
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            payload["presence_penalty"] = self.presence_penalty

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()

            # Extract the assistant's message
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                # Parse JSON response
                return json.loads(content)

            return None

        except requests.exceptions.Timeout:
            print(f"DeepSeek API timeout after {self.timeout} seconds")
            return None
        except requests.exceptions.RequestException as e:
            print(f"DeepSeek API error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to parse DeepSeek response: {e}")
            return None

    def make_decision_with_fallback(
        self, system_prompt: str, user_prompt: str, default_action: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], str]:
        """
        Make a decision with fallback to default action if API fails.

        Returns (decision, raw_response_text).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        # Add optional parameters if configured
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.frequency_penalty is not None:
            payload["frequency_penalty"] = self.frequency_penalty
        if self.presence_penalty is not None:
            payload["presence_penalty"] = self.presence_penalty

        try:
            print(f"  Making API call to DeepSeek (timeout: {self.timeout}s)...")
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()
            data = response.json()
            print(f"  API call successful!")

            # Extract the assistant's message
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return parsed, content

            print(f"  No choices in API response, using default action")
            return default_action, json.dumps(default_action)

        except requests.exceptions.Timeout:
            print(f"  API timeout after {self.timeout}s (falling back to default)")
            return default_action, json.dumps(default_action)
        except requests.exceptions.RequestException as e:
            print(f"  API request error (falling back to default): {e}")
            return default_action, json.dumps(default_action)
        except Exception as e:
            print(f"  Unexpected error (falling back to default): {e}")
            return default_action, json.dumps(default_action)
