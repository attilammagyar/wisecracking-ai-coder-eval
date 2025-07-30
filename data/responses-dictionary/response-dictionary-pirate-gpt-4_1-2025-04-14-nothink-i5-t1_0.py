# --- BEGIN GENERATED CODE ---
import collections.abc
import string

# ====== HELPERS FOR TOKEN CLASSIFICATION & NORMALIZATION ======

def is_word_token(token):
    # If it has at least one alphanumeric char, consider 'word'
    return any(c.isalnum() for c in token)

def normalize_token(token):
    # Lowercase for case-insensitive matchin'
    return token.lower()

def tokenize_phrase(phrase):
    # Split a dictionary phrase string into interleaved [word, sep, word, sep, ...]
    tokens = []
    buf = ""
    is_word = None
    for c in phrase:
        if c.isalnum():
            if is_word != True:
                if buf: tokens.append(buf)
                buf = ""
                is_word = True
            buf += c
        else:
            if is_word != False:
                if buf: tokens.append(buf)
                buf = ""
                is_word = False
            buf += c
    if buf: tokens.append(buf)
    # Now join consecutive separators or words split by this process
    result = []
    for t in tokens:
        if result and (is_word_token(result[-1]) == is_word_token(t)):
            result[-1] += t
        else:
            result.append(t)
    # Strip leading and trailing separators for phrase match control
    start = 0
    end = len(result)
    while start < end and not is_word_token(result[start]):
        start += 1
    while end > start and not is_word_token(result[end-1]):
        end -= 1
    return [normalize_token(t) if is_word_token(t) else t for t in result[start:end]]

# ====== TRIE FOR PHRASE MATCHIN' ======

class PhraseTrieNode:
    __slots__ = ("children", "entry_ids", "is_sep")
    def __init__(self, is_sep=False):
        self.children = dict()
        self.entry_ids = set()
        self.is_sep = is_sep  # True: separator node in phrase, False: word

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    # Initialize single word lookup (case-insensitive)
    word_dict = collections.defaultdict(set)
    # Root of phrase trie
    root = PhraseTrieNode()
    max_phrase_len = 1  # for optimization: max tokens any phrase might span

    for key, entry_id in dictionary.items():
        norm_key = normalize_token(key)
        norm_tokens = tokenize_phrase(key)  # Already normalizes words
        if len(norm_tokens) == 1 and is_word_token(norm_tokens[0]):
            # Single word entry
            word_dict[norm_tokens[0]].add(entry_id)
        else:
            max_phrase_len = max(max_phrase_len, len(norm_tokens))
            # Insert phrase into the trie
            node = root
            for token in norm_tokens:
                is_sep = not is_word_token(token)
                token_key = token if is_sep else normalize_token(token)
                if token_key not in node.children:
                    node.children[token_key] = PhraseTrieNode(is_sep=is_sep)
                node = node.children[token_key]
            node.entry_ids.add(entry_id)

    return {
        "word_dict": {k: set(v) for k, v in word_dict.items()},
        "phrase_trie": root,
        "max_phrase_len": max_phrase_len
    }

# ====== MATCHING ALGORITHM ======

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    n = len(tokens)
    word_dict = dictionary_index["word_dict"]
    root = dictionary_index["phrase_trie"]
    max_phrase_len = dictionary_index["max_phrase_len"]

    # Store sets of annotations for each token
    annots = [set() for _ in range(n)]

    # Build a parallel mask for word tokens
    is_word = [is_word_token(t) for t in tokens]
    norm_tokens = [normalize_token(t) if is_word[i] else t for i, t in enumerate(tokens)]

    # ----- SINGLE TOKEN DICTIONARY MATCH -----
    for i, ntok in enumerate(norm_tokens):
        if is_word[i] and ntok in word_dict:
            annots[i].update(word_dict[ntok])

    # ----- PHRASE/TRIE MATCH -----
    for start in range(n):
        # Only try starting at words or inner separators (not leading/trailing spacers)
        # But must not match phrases starting at a separator that would be considered a phrase edge
        if not is_word[start]:
            # Only allow separators to start a phrase if it's prefix in the trie (handle " , AAA" phrases)
            pass  # handled by phrase construction: leading/trailing separators pruned
        node = root
        t_idx = start
        path = []  # (idx, sepflag)
        while t_idx < n and len(path) < max_phrase_len:
            t_is_word = is_word[t_idx]
            tnorm = norm_tokens[t_idx]  # Already normalized if word, raw otherwise

            # Try word key
            if t_is_word and tnorm in node.children:
                node = node.children[tnorm]
                path.append((t_idx, False))
            # Try separator key: match ANY non-word token _in phrase_ to ANY separator in dict
            elif (not t_is_word):
                match_sep = None
                for k, child in node.children.items():
                    if child.is_sep:  # Is a separator node
                        match_sep = k
                        break  # Only one possible separator at each phrase position in dict
                if match_sep is not None:
                    node = node.children[match_sep]
                    path.append((t_idx, True))
                else:
                    break  # No matching separator expected at this trie position
            else:
                break  # No match to continue
            # On phrase match, annotate all path positions: words and inner separators.
            if node.entry_ids:
                # Find leading/trailing word tokens--for inner separator inclusion
                # Only include inner separators (not at phrase edges)
                indices = [idx for idx, _ in path]
                seg_types = [is_word[idx] for idx, _ in path]
                # First and last word positions
                first_word_idx = None
                last_word_idx = None
                for j, flag in enumerate(seg_types):
                    if flag:
                        if first_word_idx is None:
                            first_word_idx = j
                        last_word_idx = j
                # Annotate all word tokens in the span, and inner separators (strictly between first_word_idx and last_word_idx)
                for j, (token_idx, is_sep_flag) in enumerate(path):
                    if not is_sep_flag:
                        annots[token_idx].update(node.entry_ids)  # Always annotate words
                    else:
                        if first_word_idx is not None and first_word_idx < j < last_word_idx:
                            annots[token_idx].update(node.entry_ids)  # Only inner separators
            t_idx += 1

    # Form output
    return [(tokens[i], annots[i]) for i in range(n)]
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


