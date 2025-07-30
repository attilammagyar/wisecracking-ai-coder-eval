# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# -------- Helpers for normalization --------

def normalize_key(s):
    # Lowercase, collapse all non-word runs to single space, strip
    s = s.lower()
    # Replace non-word (per unicode) with a single space
    s = re.sub(r'\W+', ' ', s)
    return s.strip()

def split_phrase_by_type(s):
    """
    Splits normalized string into alternating [word, separator, word, ...]
    Non-word sequences become ' '.
    E.g., 'aaa, bbb' -> ['aaa', ' ', 'bbb']
    """
    chunks = []
    last_type = None
    for m in re.finditer(r'(\w+)|(\W+)', s):
        if m.group(1) is not None:  # Word part
            cur_type = 'word'
            val = m.group(1).lower()
        else:
            cur_type = 'sep'
            # Treat all non-words as just a single separator for matching
            val = ' '
        # Only append if type changes
        if len(chunks) == 0 or cur_type != last_type:
            chunks.append(val)
            last_type = cur_type
        else:
            # Collapse continuous seps or continuous words
            if cur_type == 'word':
                chunks[-1] += val
            # For seps, don't add extra
    return chunks

def is_word(token):
    # A token is a word if it has at least one alphanumeric character (covers more languages)
    return bool(re.match(r'\w+', token))

def normalize_token(token):
    # Lowercase only! (don't strip, keep token boundaries as-is)
    return token.lower()

# -------- Trie Structures --------

class DictPhraseTrieNode:
    __slots__ = ['children', 'entry_ids', 'part_type']
    # part_type: 'word' or 'sep'
    def __init__(self, part_type):
        self.children = dict()
        self.entry_ids = set()
        self.part_type = part_type

class DictionaryIndex:
    def __init__(self, root, single_word_map, max_phrase_len):
        self.root = root
        self.single_word_map = single_word_map # normalized_token -> set of entry_ids
        self.max_phrase_len = max_phrase_len

# --------- Initialization ---------

def build_dictionary_index(dictionary):
    # Normalize dictionary and build:
    #  - trie of phrases (using alternation word/sep/word/...)
    #  - map of single words to ids

    trie_root = DictPhraseTrieNode(part_type=None)  # None, start state
    single_word_map = dict()
    max_phrase_len = 1
    
    for key, entry_id in dictionary.items():
        phrase = key.strip().lower()
        # Split into word/sep alternation
        phrase_chunks = split_phrase_by_type(phrase)
        # Remove leading/trailing separators
        while phrase_chunks and phrase_chunks[0] == ' ':
            phrase_chunks.pop(0)
        while phrase_chunks and phrase_chunks[-1] == ' ':
            phrase_chunks.pop()
        if not phrase_chunks:
            continue
        # Insert into trie
        node = trie_root
        for i, part in enumerate(phrase_chunks):
            part_type = 'word' if i % 2 == 0 else 'sep'
            key = (part, part_type)
            if key not in node.children:
                node.children[key] = DictPhraseTrieNode(part_type=part_type)
            node = node.children[key]
        node.entry_ids.add(entry_id)
        # For single word entries, track in a map
        if len(phrase_chunks) == 1:
            w = phrase_chunks[0]
            if w not in single_word_map:
                single_word_map[w] = set()
            single_word_map[w].add(entry_id)
        max_phrase_len = max(max_phrase_len, len(phrase_chunks))
    return DictionaryIndex(trie_root, single_word_map, max_phrase_len)

# --------- Annotation Algorithm ---------

def annotate(tokens, dictionary_index):
    # tokens: iterable of strings
    # For each token, collect all entry_ids
    # Approach: for each token position, start phrase match
    # At each position, first scan for phrase matches (trie), then annotate as single word if found

    # 1. Preprocess input tokens: make a list and identify [type, normalized]
    input_tokens = []
    for t in tokens:
        typ = 'word' if is_word(t) else 'sep'
        norm = normalize_token(t)
        input_tokens.append({'token': t, 'type': typ, 'norm': norm, 'annots': set()})

    N = len(input_tokens)
    # 2. Single-word annotation step
    for idx, info in enumerate(input_tokens):
        if info['type'] == 'word':
            anns = dictionary_index.single_word_map.get(info['norm'])
            if anns:
                info['annots'].update(anns)

    # 3. Phrase annotation step: for each position, attempt to match trie
    for start in range(N):
        # Only start phrase on a "word" token
        if input_tokens[start]['type'] != 'word':
            continue
        # Start state
        node = dictionary_index.root
        span_indices = []
        cur_idx = start
        part_idx = 0  # Alternates: even = word, odd = sep
        while cur_idx < N:
            # Word expected:
            if part_idx % 2 == 0:
                # At word token?
                if input_tokens[cur_idx]['type'] != 'word':
                    break  # Mismatch
                key = (input_tokens[cur_idx]['norm'], 'word')
                if key not in node.children:
                    break
                node = node.children[key]
                span_indices.append(cur_idx)
                cur_idx += 1
                part_idx += 1
            else:
                # sep expected in phrase
                # In the input: allow any non-empty run of sep tokens, but must match at least one
                sep_start = cur_idx
                if cur_idx < N and input_tokens[cur_idx]['type'] == 'sep':
                    # Must have at least one
                    while cur_idx < N and input_tokens[cur_idx]['type'] == 'sep':
                        cur_idx += 1
                    # For the trie, sep is always ' ', so:
                    key = (' ', 'sep')
                    if key not in node.children:
                        break
                    node = node.children[key]
                    # For phrase span indices: we include *all* inner sep token indices
                    span_indices.extend(range(sep_start, cur_idx))
                    part_idx += 1
                else:
                    # No sep tokens where sep expected: stop
                    break
            # If after this, we're at phrase end (if node.entry_ids), assign phrase IDs.
            if node.entry_ids:
                # For phrase, as per spec:
                # - include both word tokens and separators inside the match
                # - but skip leading/trailing separators (i.e. at span_indices[0] and [-1], only if those tokens are sep)
                first, last = span_indices[0], span_indices[-1]
                phrase_indices = span_indices.copy()
                # Remove leading/trailing seps (but phrase always starts/ends on word token so this is mostly for multi-sep matches)
                while phrase_indices and input_tokens[phrase_indices[0]]['type'] == 'sep':
                    phrase_indices.pop(0)
                while phrase_indices and input_tokens[phrase_indices[-1]]['type'] == 'sep':
                    phrase_indices.pop()
                for pi in phrase_indices:
                    input_tokens[pi]['annots'].update(node.entry_ids)

    return [(info['token'], set(info['annots'])) for info in input_tokens]
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


