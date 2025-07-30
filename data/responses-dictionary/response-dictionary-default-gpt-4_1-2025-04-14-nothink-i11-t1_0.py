# --- BEGIN GENERATED CODE ---
import collections.abc

# Helper: Classifier for token type
def _is_word(token):
    # "Word" tokens: at least one alphanumeric char
    return any(c.isalnum() for c in token)

def _normalize_tokens(tokens):
    """
    Normalize a sequence of tokens into a list of alternating
    (is_word, value) where is_word indicates word/separator chunk
    and value is the lowercased word or generic "<SEP>" for separator.
    Multiple consecutive separators are coalesced into one.
    """
    norm = []
    buffer = []
    last_is_word = None

    for t in tokens:
        is_word = _is_word(t)
        if last_is_word is None:
            last_is_word = is_word
            buffer = [t]
        elif is_word == last_is_word:
            buffer.append(t)
        else:
            if last_is_word:
                # collapse word chunk
                norm.append( (True, ' '.join(w.lower() for w in buffer)) )
            else:
                # collapse all separators to '<SEP>'
                norm.append( (False, "<SEP>") )
            buffer = [t]
            last_is_word = is_word
    # Add final buffer
    if buffer:
        if last_is_word:
            norm.append( (True, ' '.join(w.lower() for w in buffer)) )
        else:
            norm.append( (False, "<SEP>") )
    return norm

def _dictionary_phrase_to_chunks(phrase):
    """
    Convert dict key/phrase (plain string, e.g., "the green apple")
    to a list of normalized chunks according to same normalization
    as above: alternates between (is_word, value).
    """
    # Split on whitespace and certain punctuation (keep for separator)
    import re
    # Tokenize on runs of \w+ vs non-\w+
    chunk_list = []
    for part in re.finditer(r'(\w+)|(\W+)', phrase):
        word = part.group(1)
        if word:
            chunk_list.append( (True, word.lower()) )
        else:
            # Any nonword chars = separator run
            chunk_list.append( (False, "<SEP>") )
    # Now coalesce consecutive similar types
    result = []
    buf, last_is_word = [], None
    for is_word, val in chunk_list:
        if last_is_word is None or is_word == last_is_word:
            buf.append(val)
            last_is_word = is_word
        else:
            # Flush buffer
            if last_is_word:
                # word
                result.append( (True, ' '.join(buf)) )
            else:
                result.append( (False, "<SEP>") )
            buf = [val]
            last_is_word = is_word
    if buf:
        if last_is_word:
            result.append( (True, ' '.join(buf)) )
        else:
            result.append( (False, "<SEP>") )
    # Remove leading/trailing separators (as phrases never begin/end with <SEP> semantically)
    while result and not result[0][0]:
        result = result[1:]
    while result and not result[-1][0]:
        result = result[:-1]
    return result

# Trie node class
class _TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        self.children = {}  # key: (is_word, value) -> node
        self.entries = set() # dictionary entries ending here

class _DictionaryIndex:
    """
    Holds the trie root and provides matching logic.
    """
    def __init__(self):
        self.root = _TrieNode()

    def insert(self, chunks, entry):
        """
        Insert normalized chunk list of a phrase into the trie.
        """
        node = self.root
        for chunk in chunks:
            if chunk not in node.children:
                node.children[chunk] = _TrieNode()
            node = node.children[chunk]
        node.entries.add(entry)

    def max_phrase_chunks(self):
        """
        Returns the maximum phrase length (in chunks) for optimization.
        """
        max_len = 0
        def dfs(node, cur_len):
            nonlocal max_len
            if node.entries:
                max_len = max(max_len, cur_len)
            for c in node.children.values():
                dfs(c, cur_len+1)
        dfs(self.root, 0)
        return max_len

    def match_from(self, norm_tokens, start):
        """
        Attempt to match from norm_tokens[start:]. Returns list of
        (match_end, set of entries).
        Each (match_end, entries): entries applies to norm_tokens[start:match_end].
        """
        node = self.root
        matches = []
        idx = start
        while idx < len(norm_tokens):
            chunk = norm_tokens[idx]
            if chunk not in node.children:
                break
            node = node.children[chunk]
            if node.entries:
                matches.append( (idx+1, node.entries) )
            idx += 1
        return matches

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    trie = _DictionaryIndex()
    for key, entry in dictionary.items():
        chunks = _dictionary_phrase_to_chunks(key)
        if not chunks:
            continue
        trie.insert(chunks, entry)
    return trie

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    N = len(tokens)
    annotations = [set() for _ in range(N)]
    # Precompute word/separator flags for all tokens.
    is_word_arr = [_is_word(t) for t in tokens]

    # Normalize input tokens into (is_word, value) chunks for mapping
    norm_tokens = []
    norm_map = [] # norm_map[i] = [start, end) token indices of tokens corresponding to norm_tokens[i]
    idx = 0
    while idx < N:
        is_word = is_word_arr[idx]
        start = idx
        while idx < N and is_word_arr[idx] == is_word:
            idx += 1
        if is_word:
            value = ' '.join(tokens[j].lower() for j in range(start, idx))
        else:
            value = "<SEP>"
        norm_tokens.append( (is_word, value) )
        norm_map.append( (start, idx) )
    # Now for each position in norm_tokens, attempt to match trie
    trie = dictionary_index
    L = len(norm_tokens)
    for i in range(L):
        matches = trie.match_from(norm_tokens, i)
        for end, entries in matches:
            # Map (i, end) in norm_tokens to original token indices
            tok_start = norm_map[i][0]
            tok_end = norm_map[end-1][1]
            # Determine which original tokens are word/separator
            # Annotate: all word tokens, and inner separator tokens (not leading/trailing)
            tidxs = list(range(tok_start, tok_end))
            if not tidxs:
                continue
            # Identify leading/trailing separator runs
            # By construction, within [i, end), [i] is start chunk, [end-1] is end chunk
            # Each chunk may correspond to >1 tokens
            first_chunk_is_word = norm_tokens[i][0]
            last_chunk_is_word = norm_tokens[end-1][0]
            # Mark positions for annotation:
            # All word tokens within range
            for tidx in tidxs:
                if is_word_arr[tidx]:
                    annotations[tidx].update(entries)
            # For separator chunks: only those not at the start or end
            for chunk_pos in range(i+1, end-1):
                c_is_word, _ = norm_tokens[chunk_pos]
                if not c_is_word:
                    s_start, s_end = norm_map[chunk_pos]
                    for tidx in range(s_start, s_end):
                        if not is_word_arr[tidx]:
                            annotations[tidx].update(entries)
    # For individual word/phrase entries, also annotate single-token matches
    # BUT the above approach handles single-word and multi-word.
    # Now return as required
    return [(tok, annotations[i]) for i, tok in enumerate(tokens)]
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


