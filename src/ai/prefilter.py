import hashlib
import re
import logging

logger = logging.getLogger("gigpulse.prefilter")

class PreFilter:
    def __init__(self):
        self.spam_patterns = [
            r"\b(?:шукаю|ищу)\s+(?:роботу|работу|проект(?:ы|и)?)\b",
            r"\b(?:резюме|cv|ищу\s+заказ(?:ы)?|ищу\s+клиент(?:а|ов))\b",
            r"\b(?:готов(?:а)?\s+выполнить|готов(?:ий|а)\s+виконати|available\s+for\s+work)\b",
            r"\b(?:купить|продам|продаю)\s+(?:курс|обучение|марафон)\b",
            r"\b(?:курс(?:ы|ів)?|обучени[ея]|марафон(?:а|ів)?)\b.{0,40}\b(?:купить|купуйте|запис|продаж)\b",
            r"\b(?:ищу\s+работу|шукаю\s+роботу|looking\s+for\s+(?:a\s+)?job)\b",
        ]
        self.compiled_spam = [re.compile(p, re.IGNORECASE) for p in self.spam_patterns]

    def get_hash(self, text: str, contact: str) -> str:
        normalized_text = re.sub(r"\s+", " ", text).strip().casefold()
        normalized_contact = contact.strip().casefold()
        return hashlib.sha256(f"{normalized_text}\n{normalized_contact}".encode("utf-8")).hexdigest()

    def is_spam(self, text: str) -> bool:
        for pattern in self.compiled_spam:
            if pattern.search(text):
                return True
        return False
