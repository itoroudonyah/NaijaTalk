from typing import Dict
import requests


class NLLBTranslationModel:
    """Simple API-agnostic translation for Nigerian languages.
    Uses free Google Translate API via deep_translator library.
    Falls back to simple echo translation if no API available.
    """

    def __init__(self) -> None:
        self._device = "cpu"

    def translate(self, text: str, source_abbr: str, target_abbr: str) -> str:
        """Translate text between languages.
        
        Args:
            text: Text to translate
            source_abbr: Source language code (en, yo, ha, ig)
            target_abbr: Target language code (en, yo, ha, ig)
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return ""
        
        if source_abbr == target_abbr:
            return text
        
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(
                source=source_abbr,
                target=target_abbr
            ).translate(text)
            if result:
                return result
        except ImportError:
            pass
        except Exception:
            pass
        
        try:
            lang_map = {
                "en": "english",
                "yo": "yoruba", 
                "ha": "hausa",
                "ig": "igbo"
            }
            target_name = lang_map.get(target_abbr, target_abbr)
            target_code = self._get_mymemory_code(target_abbr)
            
            response = requests.post(
                "https://api.mymemory.com/translatelanges/get",
                json={
                    "q": text,
                    "langpair": f"{source_abbr}|{target_abbr}"
                },
                timeout=10
            )
            if response.ok:
                data = response.json()
                if data.get("responseStatus") == 200:
                    translated = data.get("responseData", {}).get("translatedText", "")
                    if translated:
                        return translated
        except Exception:
            pass
        
        return self._simple_fallback_translate(text, source_abbr, target_abbr)
    
    def _get_mymemory_code(self, lang_code: str) -> str:
        """Map language codes to MyMemory format."""
        code_map = {
            "en": "en",
            "yo": "yo",
            "ha": "ha", 
            "ig": "ig"
        }
        return code_map.get(lang_code, lang_code)
    
    def _simple_fallback_translate(self, text: str, source: str, target: str) -> str:
        """Simple fallback when no translation API works."""
        prefix_map = {
            "en": "EN",
            "yo": "YO",
            "ha": "HA",
            "ig": "IG"
        }
        src = prefix_map.get(source, source.upper())
        tgt = prefix_map.get(target, target.upper())
        return f"[{src}→{tgt}] {text}"