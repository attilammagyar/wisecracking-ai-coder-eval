# --- BEGIN GENERATED CODE ---
import collections.abc

class _TrieNode:
    __slots__ = ("children", "terminals", "prefixes", "nid")
    def __init__(self, nid: int):
        self.children: dict[str, _TrieNode] = {}
        self.terminals: set = set()
        self.prefixes: set[str] = set()
        self.nid: int = nid

def _is_word_token(tok: str) -> bool:
    # A token is a word if all its characters are alphanumeric (and non-empty).
    # This keeps behavior simple, fast, and matches the tests.
    if not tok:
        return False
    for ch in tok:
        if not ch.isalnum():
            return False
    return True

def _split_words(s: str) -> list[str]:
    # Split a string into runs of alphanumeric characters; lowercase for normalization.
    words = []
    cur = []
    for ch in s:
        if ch.isalnum():
            cur.append(ch.lower())
        else:
            if cur:
                words.append("".join(cur))
                cur = []
    if cur:
        words.append("".join(cur))
    return words

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie index keyed by sequences of words (alnum runs, lowercased).
    """
    # Root node
    next_id = 0
    root = _TrieNode(next_id)
    next_id += 1

    # Keep track of all nodes to compute prefixes later.
    all_nodes = [root]

    def get_child(node: _TrieNode, word: str) -> _TrieNode:
        nonlocal next_id, all_nodes
        child = node.children.get(word)
        if child is None:
            child = _TrieNode(next_id)
            next_id += 1
            node.children[word] = child
            all_nodes.append(child)
        return child

    for key, value in dictionary.items():
        words = _split_words(key)
        if not words:
            continue  # ignore entries that have no alnum words
        node = root
        for w in words:
            node = get_child(node, w)
        node.terminals.add(value)

    # Precompute prefix sets at each node for fast token-concatenation matching.
    for node in all_nodes:
        if not node.children:
            node.prefixes = set()
            continue
        # Include all prefixes (including full words) of each child word.
        pref = set()
        for w in node.children.keys():
            for i in range(1, len(w) + 1):
                pref.add(w[:i])
        node.prefixes = pref

    return root

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens using the trie index. For each token, return (token, set_of_ids).
    """
    tokens = list(tokens)
    n = len(tokens)
    if n == 0:
        return []

    root: _TrieNode = dictionary_index  # type: ignore[assignment]

    is_word = [_is_word_token(t) for t in tokens]
    lower_tok = [t.lower() for t in tokens]
    annotations = [set() for _ in range(n)]

    # Cache: (node.nid, start_index) -> list of (end_index, child_node)
    comp_cache: dict[tuple[int, int], list[tuple[int, _TrieNode]]] = {}

    # Cache: end_index -> next word index after at least one separator, or None
    next_word_after_sep_cache: dict[int, int | None] = {}

    def next_word_after_sep(end_idx: int) -> int | None:
        res = next_word_after_sep_cache.get(end_idx, None if end_idx in next_word_after_sep_cache else ... )
        if res is not ...:
            return res
        i = end_idx + 1
        if i >= n:
            next_word_after_sep_cache[end_idx] = None
            return None
        if is_word[i]:
            # No separator between words -> cannot proceed to next component
            next_word_after_sep_cache[end_idx] = None
            return None
        # There is at least one separator; skip all separators to the next word
        while i < n and not is_word[i]:
            i += 1
        if i < n and is_word[i]:
            next_word_after_sep_cache[end_idx] = i
            return i
        next_word_after_sep_cache[end_idx] = None
        return None

    def component_matches(node: _TrieNode, start_idx: int) -> list[tuple[int, _TrieNode]]:
        """
        From start_idx (must be a word token), find all ways to match exactly one
        dictionary 'word' (child edge) by concatenating one or more adjacent word tokens.
        Returns list of (end_index_of_component, child_node).
        """
        key = (node.nid, start_idx)
        if key in comp_cache:
            return comp_cache[key]

        res: list[tuple[int, _TrieNode]] = []
        if not (0 <= start_idx < n and is_word[start_idx]):
            comp_cache[key] = res
            return res

        # Accumulate across adjacent word tokens while the concatenation remains a prefix of some child word.
        accum = ""
        j = start_idx
        while j < n and is_word[j]:
            accum += lower_tok[j]
            if accum in node.children:
                res.append((j, node.children[accum]))
            if accum in node.prefixes:
                j += 1
                continue
            else:
                break

        comp_cache[key] = res
        return res

    def annotate_span(start_idx: int, end_idx: int, entry_id):
        for i in range(start_idx, end_idx + 1):
            annotations[i].add(entry_id)

    # Depth-first expansion from each word start
    def extend_matches(start_word_idx: int):
        """
        Start matching phrases from the word token at start_word_idx.
        """
        # Stack for manual DFS to avoid recursion limits:
        # Each frame: (node, comp_start_idx, phrase_start_idx)
        # Where comp_start_idx is where the next dictionary word component starts.
        stack: list[tuple[_TrieNode, int, int]] = [(root, start_word_idx, start_word_idx)]

        while stack:
            node, comp_start_idx, phrase_start_idx = stack.pop()

            for end_idx, child in component_matches(node, comp_start_idx):
                # Any phrase ending here?
                if child.terminals:
                    for entry_id in child.terminals:
                        annotate_span(phrase_start_idx, end_idx, entry_id)

                # Try to continue to the next dictionary word (requires at least one separator in the text)
                nxt = next_word_after_sep(end_idx)
                if nxt is not None:
                    stack.append((child, nxt, phrase_start_idx))

    # Launch matching from each word token position
    for s in range(n):
        if is_word[s]:
            extend_matches(s)

    return [(tokens[i], annotations[i]) for i in range(n)]
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


