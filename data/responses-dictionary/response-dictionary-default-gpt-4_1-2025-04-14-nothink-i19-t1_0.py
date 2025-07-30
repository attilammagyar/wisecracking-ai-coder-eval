# --- BEGIN GENERATED CODE ---
import collections.abc

def _is_word(token):
    """Return True if token is a word token."""
    # Accept as word if token has any alphanum character (robust for markdown, emoji, etc)
    # You may tune this logic as needed.
    return any(c.isalnum() for c in token)

def _normalize(token):
    return token.casefold()

class TrieNode:
    __slots__ = ['children', 'entry_ids']
    def __init__(self):
        self.children = {} # key: normalized token or SEP, value: TrieNode
        self.entry_ids = set() # set of associated dictionary entry ids

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie index from a dictionary.
    """
    SEP = '<SEP>'
    root = TrieNode()
    word2ids = collections.defaultdict(set)
    max_entry_len = 1

    for key, entry_id in dictionary.items():
        # Split into "word" and "separator" segments
        splits = []
        buf = ''
        last_was_word = None
        for ch in key:
            if ch.isspace() or not ch.isalnum():
                if buf:
                    splits.append((True, buf))
                    buf = ''
                splits.append((False, ch))
                last_was_word = False
            else:
                buf += ch
                last_was_word = True
        if buf:
            splits.append((True, buf))

        # Now group consecutive separators as one SEP, and words to normalized form
        components = []
        i = 0
        L = len(splits)
        while i < L:
            is_word, seg = splits[i]
            if is_word:
                components.append(_normalize(seg))
                i += 1
            else:
                # gather consecutive non-words
                while i < L and not splits[i][0]:
                    i += 1
                components.append(SEP)

        # Save maximal length for efficient search
        if len(components) > max_entry_len:
            max_entry_len = len(components)

        # Add to trie
        node = root
        for comp in components:
            if comp not in node.children:
                node.children[comp] = TrieNode()
            node = node.children[comp]
        node.entry_ids.add(entry_id)
        
        # Add individual word mappings
        # Only for single-word entries. Don't put phrases (contains SEP) here.
        if len(components) == 1 and components[0] != SEP:
            word2ids[components[0]].add(entry_id)

    return {
        'root': root,
        'SEP': SEP,
        'word2ids': {k: set(v) for k, v in word2ids.items()},
        'max_len': max_entry_len
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the trie dictionary index.
    """
    if not tokens:
        return []

    root = dictionary_index['root']
    SEP = dictionary_index['SEP']
    word2ids = dictionary_index['word2ids']
    max_entry_len = dictionary_index['max_len']

    # Precompute token classifications and normalizations
    tokens = list(tokens)
    N = len(tokens)
    is_word = [_is_word(tok) for tok in tokens]
    norm_tokens = [_normalize(tok) for tok in tokens]

    # Track, for each token, the set of entry ids it should be annotated with
    annotations = [set() for _ in range(N)]

    # 1. Annotate single word tokens
    for idx, (tok, iw, norm) in enumerate(zip(tokens, is_word, norm_tokens)):
        if iw:
            ids = word2ids.get(norm)
            if ids:
                annotations[idx].update(ids)

    # 2. Perform multi-token phrase matching
    # For efficiency, don't check past where there's enough tokens for a maxlen entry
    # Because phrase matching can overlap, we need to handle multiple overlapping matches
    
    # To enable flexible matching of separator tokens:
    #   - Dictionary entries treat all separators as one "slot", so sequence of 1+ separator tokens matches a single 'SEP'
    #   - Matching process must be able to skip over 1+ separator tokens for any dict SEP
    #   - But leading/trailing separators are not annotated if not part of phrase.
    #

    for start in range(N):
        node = root
        i = start
        token_positions = []  # list of (is_word, token_idx), only for phrase tokens in the match
        matched_positions = []  # indices of tokens considered part of the matched phrase (for annotation)
        while i < N:
            if is_word[i]:
                key = norm_tokens[i]
                if key in node.children:
                    node = node.children[key]
                    token_positions.append((True, i))
                    matched_positions.append(i)
                else:
                    break
                i += 1
            else:
                # Separator span: If the current trie has a SEP branch, must match at least one non-word token
                if SEP in node.children:
                    if i == start:
                        # Separator at phrase start; don't match phrases starting from a separator
                        break
                    node = node.children[SEP]
                    matched_sep_start = i
                    # Advance through all consecutive separators as a single SEP
                    while i < N and not is_word[i]:
                        i += 1
                    # Record matched separator (potentially multi-token) range
                    for sep_idx in range(matched_sep_start, i):
                        token_positions.append((False, sep_idx))
                        matched_positions.append(sep_idx)
                else:
                    break
            # After adding, check if this node is accepting (end of phrase)
            if node.entry_ids:
                # We're pointing at the last token in phrase; phrase is from start to i-1
                # Now: annotate all tokens in matched_positions except leading/trailing separators
                if matched_positions:
                    first = 0
                    last = len(matched_positions)-1
                    # leading separator(s)
                    while first <= last and not is_word[matched_positions[first]]:
                        first += 1
                    # trailing separator(s)
                    while last >= first and not is_word[matched_positions[last]]:
                        last -= 1
                    # annotate all inner tokens (between first and last inclusive)
                    for pos in range(first, last+1):
                        idx = matched_positions[pos]
                        annotations[idx].update(node.entry_ids)
                    # Inner separators (not leading or trailing): also get entry_id
                    # Note, this matches spec: "Separators in a compound phrase should also be annotated,
                    # but only the inner ones, never the leading or trailing separators".
        # end while
    # end for start
    return list(zip(tokens, annotations))
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


