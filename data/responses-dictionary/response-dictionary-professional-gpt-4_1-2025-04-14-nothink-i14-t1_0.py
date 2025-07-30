# --- BEGIN GENERATED CODE ---
import collections.abc
import re
from typing import Dict, Set, List, Tuple, Optional, Any

# Helpers for recognizing word tokens
_WORD_REGEX = re.compile(r'\w')

def _is_word_token(token: str) -> bool:
    # Consider a token to be a 'word' if it contains at least one word character (letter/digit/underscore)
    return bool(_WORD_REGEX.search(token))

def _normalize(token: str) -> str:
    return token.lower()

# Trie node for phrase dictionary
class _PhraseTrieNode:
    __slots__ = ['children', 'phrase_ids']
    def __init__(self):
        self.children: Dict[Any, '_PhraseTrieNode'] = {}
        self.phrase_ids: Set[Any] = set()  # Set of entry IDs for phrases ending at this node

# Utility class bundling the index structures
class _DictionaryIndex:
    def __init__(self):
        self.word_index: Dict[str, Set[Any]] = {}  # word -> set(entry_ids)
        self.phrase_trie = _PhraseTrieNode()
        self.max_phrase_length: int = 1  # At least 1

# Tokenizing dictionary keys to sequence of "word"/"sep"/"word"/... tokens
def _split_dict_phrase(phrase: str) -> List[Tuple[str, bool]]:
    """
    Split a dictionary phrase (e.g., "AAA, BBB") into a list of (token, is_word)
    Used for inserting into the phrase trie.
    """
    tokens = []
    curr = ""
    curr_is_word = None
    for ch in phrase:
        if _is_word_token(ch):
            if curr_is_word is False:
                if curr:
                    tokens.append((curr, False))
                curr = ch
                curr_is_word = True
            else:
                curr += ch
                curr_is_word = True
        else:
            if curr_is_word is True:
                if curr:
                    tokens.append((curr, True))
                curr = ch
                curr_is_word = False
            else:
                curr += ch
                curr_is_word = False
    if curr:
        tokens.append((curr, curr_is_word))
    return tokens

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and compound phrases.
    """
    index = _DictionaryIndex()
    for key, entry_id in dictionary.items():
        key = key.strip()
        if not key:
            continue
        key_tokens = _split_dict_phrase(key)
        # Check if it's a single token phrase with only word characters
        if len(key_tokens) == 1 and key_tokens[0][1]:
            # Single-word entry
            word = _normalize(key_tokens[0][0])
            index.word_index.setdefault(word, set()).add(entry_id)
        else:
            # Multi-token (at least one word, maybe with separators)
            node = index.phrase_trie
            length = 0
            for token, is_word in key_tokens:
                if is_word:
                    t = ('WORD', _normalize(token))
                    length += 1
                else:
                    t = ('SEP',)  # Treat all separators the same; will match any sep in input
                if t not in node.children:
                    node.children[t] = _PhraseTrieNode()
                node = node.children[t]
            node.phrase_ids.add(entry_id)
            if length > index.max_phrase_length:
                index.max_phrase_length = length
    return index

def annotate(
    tokens: collections.abc.Iterable[str], 
    dictionary_index: object
) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    index: _DictionaryIndex = dictionary_index
    tokens = list(tokens)  # In case it's a generator
    n = len(tokens)
    # Initialize annotation sets for each token
    annotations: List[Set[Any]] = [set() for _ in tokens]
    # Record token types ahead of time
    token_types: List[bool] = [_is_word_token(t) for t in tokens]

    # 1. Annotate individual tokens (single-word entries)
    for i, token in enumerate(tokens):
        if token_types[i]:
            t_norm = _normalize(token)
            s = index.word_index.get(t_norm)
            if s:
                annotations[i].update(s)

    # 2. Annotate compound phrases via phrase trie
    # For each possible start word position
    for i in range(n):
        if not token_types[i]:
            continue  # start only at word tokens
        # We need to try to walk the trie from i as start
        trie_nodes = [(index.phrase_trie, i, i)]  # (current_node, token_idx, first_word_idx)
        while trie_nodes:
            node, j, anchor = trie_nodes.pop()
            pos = j
            # We want to support sequences of: WORD, (SEP, WORD)... without leading/trailing separators
            curr_node = node
            word_consumed = False
            k = pos
            last_word_idx = None
            # We build a sequence matching the trie, alternating word/sep nodes
            while True:
                if k >= n:
                    break
                tt = token_types[k]
                t = tokens[k]
                if tt:
                    # word token
                    label = ('WORD', _normalize(t))
                    if label in curr_node.children:
                        curr_node2 = curr_node.children[label]
                        last_word_idx = k
                        word_consumed = True
                        # If this node is an accepting state, annotate all relevant tokens
                        if curr_node2.phrase_ids:
                            # Determine the span to annotate:
                            # - from anchor...k
                            # - annotate all toens in [anchor, k] including inner separators
                            # - only if leading/trailing are word tokens:
                            #   - leading must be word (by construction)
                            #   - trailing must be word (by k now at word)
                            # - annotate [anchor:k+1]
                            for pid in curr_node2.phrase_ids:
                                for idx in range(anchor, k+1):
                                    # Only annotate leading/trailing separators *not* if at edges
                                    # We will handle leading/trailing separators by not letting anchor/k land on a separator
                                    if idx == anchor or idx == k:
                                        # always included, both are WORD tokens here
                                        pass
                                    annotations[idx].add(pid)
                            # Continue trying to extend, as there may be nested phrases
                        # Now look for possible separator after this word (to match next trie child)
                        if ('SEP',) in curr_node2.children:
                            # Try to match one or more separator tokens followed by another word
                            sep_k = k+1
                            sep_encountered = False
                            while sep_k < n and not token_types[sep_k]:
                                sep_encountered = True
                                # We'll match as many separators as there are, moving forward, looking for the next word
                                # But we need to continue in the trie under the SEP edge
                                trie_nodes.append((curr_node2.children[('SEP',)], sep_k, anchor))
                                sep_k += 1
                        # Advance to try to match further words, if any
                        if ('WORD', _normalize(t)) in curr_node.children:
                            # Redundant, but let's avoid infinite loop
                            pass
                        # Break after first word match, unless we also have self-loop for repeated words (rare)
                        # But the trie structure as constructed won't create self-loops
                        break
                    else:
                        break  # No word match possible, quit inner
                else:
                    break  # When matching from a word token in trie, cannot start by matching a sep token

    # 3. Annotate compound phrases with arbitrary separators (SEP inside phrase)
    # To support for cases where e.g. "AAA, BBB" in the dictionary matches tokens ["AAA", " ", "*", "BBB"],
    # as in test_compound_phrases_word_separation, we need to allow arbitrary number of non-word tokens
    # in place of a "SEP" in trie.

    # For this, we'll use a BFS approach for matching from each word token start position.
    for start in range(n):
        if not token_types[start]:
            continue
        stack = [ (index.phrase_trie, start, start, start) ]  # (node, pos, phrase_first_word_idx, last_word_idx)
        while stack:
            node, pos, phrase_first, last_word = stack.pop()
            if pos >= n:
                continue
            # First, try matching a WORD from pos if possible
            if token_types[pos]:
                label = ('WORD', _normalize(tokens[pos]))
                if label in node.children:
                    node2 = node.children[label]
                    last_word2 = pos
                    # Accepting state: annotate the phrase
                    for pid in node2.phrase_ids:
                        # Phrase spans from phrase_first to last_word2 (inclusive),
                        # annotate all tokens in that interval, including any inner separators.
                        # * But skip if phrase is preceded or followed by separator (i.e., leading/trailing).
                        # - But since start/pos are always word-index by our loop, we're safe on leading
                        # - For trailing, handled by only annotating through last word
                        for idx in range(phrase_first, last_word2+1):
                            # According to spec, annotate inner separators, always skip leading and trailing separators
                            annotations[idx].add(pid)
                    # After word, try matching SEP (arbitrary sequence of non-word tokens)
                    if ('SEP',) in node2.children:
                        sep_pos = pos + 1
                        first_sep = True
                        while sep_pos < n and not token_types[sep_pos]:
                            stack.append( (node2.children[('SEP',)], sep_pos, phrase_first, last_word2) )
                            sep_pos += 1
                    # After word, try to match another WORD directly  (for phrases without separator)
                    stack.append( (node2, pos+1, phrase_first, last_word2))
            # Now, try matching SEP at pos if possible & currently in SEP-eligible node
            if ('SEP',) in node.children and not token_types[pos]:
                # Consume the sep, stay in SEP node, but don't update last_word
                stack.append( (node.children[('SEP',)], pos+1, phrase_first, last_word))
            # Done.

    # 4. Clean up leading/trailing separators: edge case, in test_leading_and_trailing_separators_around_compound_phrase
    # Remove annotations for tokens which are separators and at the edges of a phrase.
    # But our logic above never starts matching from a separator, and never ends matching at a separator,
    # so this is handled by construction.

    # Prepare output
    return [ (token, frozenset(ann)) for token, ann in zip(tokens, annotations) ]
# --- END GENERATED CODE ---

def test_empty_sentence():
    dictionary = {}
    tokens = []

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = []
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_not_in_dictionary():
    """
    When a token is not found in the dictionary
    then it should not be annotated with anything.
    """
    dictionary = {}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_found_in_dictionary():
    """
    When a token is found in the dictionary
    then the token should be annotated with its dictionary entry.
    """
    dictionary = {"AAA": 1}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_case_insensitive_dictionary_lookup():
    """
    Dictionary lookup should be case-insensitive.
    """
    dictionary = {"AAA": 1, "BBB": 2}
    tokens = ["Aaa", "bbb"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("Aaa", {1}), ("bbb", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase():
    """
    All tokens in a compound phrase which is found in the dictionary
    should be annotated with the dictionary entry of the phrase.
    """
    dictionary = {"AAA BBB": 1}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_and_individual_word():
    """
    When a token is found in the dictionary both as an individual word and as part of a compound phrase
    then its annotations should include the dictionary entries of both the phrase and the individual word as well.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrases_word_separation():
    """
    Compound phrase dictionary lookup should be insensitive to word separators.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA, BBB": 3}
    tokens = ["AAA", " ", "*", "BBB", "*"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("*", {3}),("BBB", {3, 2}), ("*", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_leading_and_trailing_separators_around_compound_phrase():
    """
    The leading and trailing word separators should not be considered
    parts of a compound phrase.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = [" ", "AAA", " ", "BBB", " "]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [(" ", set()), ("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2}), (" ", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_separated_tokens_do_not_make_a_compound_word():
    """
    When tokens are separated by non-word characters
    then they should not be considered a compound word.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAABBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", set()), ("BBB", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_word_tokens_missing_from_dictionary():
    """
    Compound words may contain tokens which are not listed in the dictionary
    as individual words.
    """
    dictionary = {"AAABBB": 1}
    tokens = ["AAA", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_overlap():
    """
    Tokens in overlapping compound phrases should be annotated with the
    dictionary entries for all compound phrases in which they participate.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "AAA BBB": 4,
        "BBB CCC": 5,
        "CCC CCC": 6,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "CCC", " ", "CCC"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {4, 1}),
        (" ", {4}),
        ("BBB", {5, 4, 2}),
        (" ", {5}),
        ("CCC", {6, 5, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_nested_compound_phrases():
    """
    When a compound phrase itself is a part of a larger compound phrase
    then its tokens should be annotated with the dictionary entries for all the nested compound phrases.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "DDD": 4,
        "EEE": 5,
        "AAA BBB CCC DDD EEE": 6,
        "BBB CCC DDD": 7,
        "BBB CCC": 8,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "DDD", " ", "EEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {6, 1}),
        (" ", {6}),
        ("BBB", {6, 7, 8, 2}),
        (" ", {6, 7, 8}),
        ("CCC", {6, 7, 8, 3}),
        (" ", {6, 7}),
        ("DDD", {6, 7, 4}),
        (" ", {6}),
        ("EEE", {6, 5}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_no_midtoken_match():
    """
    Dictionary entry match must occur at token end.
    """
    dictionary = {"AA": 1, "AAA BBB": 2, "CC": 3, "CCCDDD": 4}
    tokens = ["AAA", " ", "BBBCCC", "CCC", "DDDEEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set()), (" ", set()), ("BBBCCC", set()), ("CCC", set()), ("DDDEEE", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_real_life_example():
    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("A", {1}),
        (" ", set()),
        ("black", {2, 4, 6}),
        (" ", {4, 6}),
        ("swan", {3, 4, 6}),
        (" ", {6}),
        ("event", {5, 6}),
        (" ", set()),
        ("would", {7}),
        (" ", set()),
        ("occur", {8}),
        (" ", set()),
        ("less", {9}),
        (" ", set()),
        ("than", {10}),
        (" ", set()),
        ("once", {11, 16}),
        (" ", {16}),
        ("in", {12, 16}),
        (" ", {16}),
        ("a", {1, 16}),
        (" ", {16}),
        ("blue", {13, 15, 16}),
        (" ", {15, 16}),
        ("moon", {14, 15, 16}),
        (".", set()),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def perf_test():
    import random
    import time

    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]
    letters = "abcdefghijklmnopqrstuvwxyz"

    while len(dictionary) < 1000:
        random_word = "".join([random.choice(letters) for i in range(15)])
        random_expr = (
            "".join([random.choice(letters) for i in range(7)])
            + " "
            + "".join([random.choice(letters) for i in range(7)])
        )
        dictionary[random_word] = len(dictionary)
        dictionary[random_expr] = len(dictionary)

    for i in range(6):
        tokens = tokens + tokens

    begin = time.time()

    for i in range(100):
        tokens_copy = list(tokens)
        dictionary_copy = dict(dictionary)
        dictionary_index = build_dictionary_index(dictionary_copy)
        annotated_tokens = list(annotate(tokens_copy, dictionary_index))

    end = time.time()

    return end - begin


def run_tests():
    import json
    import sys

    module = sys.modules[__name__]

    tests = []

    for name, value in globals().items():
        if name.startswith("test_") and callable(value) and value.__code__.co_argcount == 0:
            tests.append(value)

    passed = 0
    failed = 0
    failures = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            failures.append(f"{type(exc)} {exc}")

    perf = perf_test()

    results = {
        "passed": passed,
        "failed": failed,
        "perf": perf,
        "failures": failures,
    }

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_tests()


