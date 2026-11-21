from __future__ import annotations

import re
import unicodedata


_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch", "छ": "chh",
    "ज": "j", "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b",
    "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh",
    "स": "s", "ह": "h", "ळ": "l",
}
_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e",
}
_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e",
    "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}
_COMMON = {
    "है": "hai", "हैं": "hain", "हूँ": "hoon", "हूं": "hoon", "में": "mein", "मैं": "main",
    "क्या": "kya", "कैसे": "kaise", "कहाँ": "kahan", "कहां": "kahan", "नहीं": "nahi", "नही": "nahi",
    "और": "aur", "भाई": "bhai", "यार": "yaar", "अरे": "arre", "हाँ": "haan", "हां": "haan",
    "नमस्ते": "namaste", "ठीक": "theek", "अच्छा": "accha", "चलो": "chalo", "क्यों": "kyun",
    "तुम": "tum", "आप": "aap", "मुझे": "mujhe", "मेरा": "mera", "मेरी": "meri", "करना": "karna",
}
_VIRAMA = "्"
_NUKTA = "़"
_ANUSVARA = {"ं", "ँ"}


def _romanize_word(word: str) -> str:
    word = unicodedata.normalize("NFC", word)
    if word in _COMMON:
        return _COMMON[word]
    syllables: list[list[str | None]] = []
    index = 0
    while index < len(word):
        character = word[index]
        if character in _VOWELS:
            syllables.append(["", _VOWELS[character], ""])
            index += 1
            continue
        if character in _CONSONANTS:
            cluster = _CONSONANTS[character]
            index += 1
            if index < len(word) and word[index] == _NUKTA:
                cluster = {"क": "q", "ग": "gh", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f"}.get(character, cluster)
                index += 1
            while index < len(word) and word[index] == _VIRAMA:
                index += 1
                if index < len(word) and word[index] in _CONSONANTS:
                    cluster += _CONSONANTS[word[index]]
                    index += 1
                    if index < len(word) and word[index] == _NUKTA:
                        index += 1
                else:
                    break
            vowel: str | None = None
            if index < len(word) and word[index] in _MATRAS:
                vowel = _MATRAS[word[index]]
                index += 1
            syllables.append([cluster, vowel, ""])
            continue
        if character in _ANUSVARA:
            if syllables:
                syllables[-1][2] = "n"
            index += 1
            continue
        if character == "ः":
            if syllables:
                syllables[-1][2] = "h"
            index += 1
            continue
        index += 1

    inherent = [syllable[1] is None and bool(syllable[0]) for syllable in syllables]
    drop_schwa = [False] * len(syllables)
    if len(syllables) > 1 and inherent and inherent[-1]:
        drop_schwa[-1] = True
    for position in range(len(syllables) - 2, 0, -1):
        if inherent[position] and not drop_schwa[position + 1]:
            drop_schwa[position] = True

    result = ""
    for position, (consonant, vowel, nasal) in enumerate(syllables):
        if vowel is None and consonant:
            vowel = "" if drop_schwa[position] else "a"
        result += str(consonant or "") + str(vowel or "") + str(nasal or "")
    if len(result) > 3:
        result = re.sub(r"aa$", "a", result)
    result = re.sub(r"ee$", "i", result)
    return result


def to_hinglish(text: str) -> str:
    """Write Devanagari words in Latin script while preserving Latin words and punctuation."""
    parts = re.split(r"([ऀ-ॿ]+)", text)
    return "".join(_romanize_word(part) if re.search(r"[ऀ-ॿ]", part) else part for part in parts)
