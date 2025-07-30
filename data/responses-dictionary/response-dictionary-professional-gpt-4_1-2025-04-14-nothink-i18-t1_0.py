# --- BEGIN GENERATED CODE ---
import collections.abc

# --- Helper definitions ---

def is_word(token):
    # A "word" token contains at least one alphanumeric character.
    # This applies to both dictionary parsing and to the input tokens.
    return any(c.isalnum() for c in token)

def normalize_token(token):
    # Lowercase for case-insensitive matching
    return token.lower()

def phrase_tokenize(phrase_string):
    # Split phrase e.g. "hello, world!" -> ["hello", ",", "world", "!"]
    # We'll treat a "run" of alnum as a word, else as a separator
    import re
    # Split with group to keep separators; note: phrase_string is already a single phrase from the dictionary
    return re.findall(r'\w+|[^\w\s]', phrase_string, re.UNICODE) if phrase_string != " " else [" "]

def tokenize_string_to_wordsep(s):
    # Tokenize and mark each as word or separator, returns list of (token, is_word) pairs.
    # Split on alnums, preserve whitespace and punctuation as separate tokens.
    # Note: Input text tokens may be already tokenized, but here we're tokenizing dictionary strings for the index.
    tokens = []
    buff = ''
    last_word = None
    for c in s:
        w = c.isalnum()
        if buff and ((last_word is not None and w != last_word) or (w and last_word is None)):
            tokens.append(buff)
            buff = ''
        buff += c
        last_word = w
    if buff:
        tokens.append(buff)
    # Now, tag word/separator
    return [(t, is_word(t)) for t in tokens]

# --- Trie datastructure for phrases ---

class TrieNode:
    __slots__ = ['children', 'entries']

    def __init__(self):
        self.children = dict()
        # Set of dictionary IDs mapping to this phrase [may have >1 for semiduplicated phrases]
        self.entries = set()

def build_dictionary_index(dictionary: collections.abc.Mapping):
    """
    Build trie for fast compound phrase/word lookup.
    """
    # The trie root; each path is a list of (normalized token, is_word) pairs.
    trie_root = TrieNode()
    # For O(1) single word lookup
    word_map = dict()

    # Preprocessing: for dictionary, split phrases into tokens and
    # build trie as well as word dictionary.

    for key, entry_id in dictionary.items():
        # Tokenize the phrase into word/separator tokens, mark word boundaries
        # Use re to split, but mark is_word
        # E.g. "AAA, BBB" -> ["AAA", ",", " ", "BBB"]
        import re
        # Use \s+ as separator, but keep punctuation too
        tokens = []
        # Use python's \w+ and \W+ to capture word and non-word tokens, \s captures spaces as "non-word"
        # To allow for separators such as "," or spaces, keep all strictly
        token_matches = re.finditer(r'\w+|\s+|[^\w\s]', key, re.UNICODE)
        for m in token_matches:
            tokens.append(m.group(0))
        path = []
        for tok in tokens:
            norm = normalize_token(tok)
            path.append((norm, is_word(tok)))
        # Insert path into trie
        node = trie_root
        for part in path:
            if part not in node.children:
                node.children[part] = TrieNode()
            node = node.children[part]
        node.entries.add(entry_id)

        # Add single-word entry (if phrase is a single word)
        if len([1 for t, isw in path if isw]) == 1 and all(isw or t.isspace() for t, isw in path):
            # All else are spaces or non-words
            word_idx = [i for i, (t, isw) in enumerate(path) if isw][0]
            norm_word = path[word_idx][0]
            word_map.setdefault(norm_word, set()).add(entry_id)

    # Additionally, add all single word dictionary entries (those whose keys are a single word, ignore phrase)
    for key, entry_id in dictionary.items():
        if is_word(key) and all(c.isalnum() or c == ' ' for c in key):
            norm_key = normalize_token(key)
            word_map.setdefault(norm_key, set()).add(entry_id)

    return {
        'trie': trie_root,
        'word_map': word_map,
        # For clarity, max phrase token length for windowing could be stored, but not vital
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object):
    """
    Annotate tokens with entries from the dictionary.
    """
    trie = dictionary_index['trie']
    word_map = dictionary_index['word_map']

    # Preprocess input tokens: normalize their lower-cased value and is_word flag
    norm_tokens = []
    for tok in tokens:
        norm = normalize_token(tok)
        wordf = is_word(tok)
        norm_tokens.append((tok, norm, wordf))  # Keep original, normed, is_word

    # For each token, record sets of annotation IDs
    annotations = [set() for _ in range(len(norm_tokens))]

    # Pass 1: single-token (word) matches
    for i, (tok, norm, wordf) in enumerate(norm_tokens):
        if wordf and norm in word_map:
            annotations[i].update(word_map[norm])

    # Pass 2: compound phrase matches using the trie, annotate all participant tokens (inner separators only)
    n = len(norm_tokens)
    for start in range(n):
        # Only attempt to start phrase at word token
        if not norm_tokens[start][2]:
            continue  # skip, do not start phrase at separator
        node = trie
        end = start
        match_entries = None  # set of IDs for current phrase
        inside_phrase_indices = []
        longest_match = None  # (end index, entries, participant_indices)
        while end < n:
            curr_norm, curr_is_word = norm_tokens[end][1], norm_tokens[end][2]
            child_key = (curr_norm, curr_is_word)
            if child_key not in node.children:
                break
            node = node.children[child_key]
            inside_phrase_indices.append(end)
            # Only consider matches that start with a word and end with a word (see tests)
            # and phrase is at least two word tokens for compound; but also allow single-word as a degenerate
            if node.entries:
                # Find boundaries of phrase (indexes start..end), but we may have leading/trailing separators
                first, last = inside_phrase_indices[0], inside_phrase_indices[-1]
                # Find first and last word tokens in [first, last]
                # If start, end token are words, it's a valid span
                if norm_tokens[first][2] and norm_tokens[last][2]:
                    # For annotation, per test spec, annotate all in span except leading/trailing separators
                    # Find real annotation span (indexes annot_start..annot_end),
                    # but only the inner tokens, not leading/trailing separators.
                    # We'll include all from first to last, and mark which positions should get entries
                    span = inside_phrase_indices
                    # exclude leading separators (shouldn't happen since we only start on word),
                    # and trailing separators
                    s_idx, e_idx = 0, len(span) - 1
                    # leading: not needed, since we only start on word; but check for trailing separators
                    # trailing: only annotate if is_word or if not last token
                    # So: mark all span tokens, but if token is leading or trailing separator, do not annotate
                    for i_idx in range(s_idx, e_idx + 1):
                        idx = span[i_idx]
                        # leading or trailing separators are excluded
                        if i_idx == 0 or i_idx == e_idx:
                            # Only annotate if token is word
                            if norm_tokens[idx][2]:
                                for eid in node.entries:
                                    annotations[idx].add(eid)
                        else:
                            # Inner tokens: annotate all
                            for eid in node.entries:
                                annotations[idx].add(eid)
                    # Allow for overlapping/longest matches, so continue forward
            end += 1

    # Output as list of (original token, set of annotation IDs)
    return [(norm_tokens[i][0], annotations[i]) for i in range(n)]
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


