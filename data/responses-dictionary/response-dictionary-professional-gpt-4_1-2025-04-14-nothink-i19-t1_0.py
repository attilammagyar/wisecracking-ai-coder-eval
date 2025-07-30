# --- BEGIN GENERATED CODE ---
import collections.abc
import string

# --- Helper functions ---

def is_word_token(tok: str) -> bool:
    """
    Heuristic: A word token contains at least one alphanumeric character.
    Non-word tokens are all else (punctuation, whitespace, markdown, etc).
    """
    return any(c.isalnum() for c in tok)

def normalize_token(tok: str) -> str:
    """Normalize for dictionary and lookup. Case-insensitive."""
    return tok.lower()

def dictionary_phrase_slots(s: str):
    """
    For a dictionary key (phrase), produce a list of (slot_kind: 'word'/'sep', value) items:
      - Consecutive alnums become one slot ('word', word)
      - Runs of non-alnum become single 'sep' slots (with value None)
    E.g. "AAA, BBB" -> [('word','aaa'),('sep',None),('word','bbb')]
    """
    res = []
    pos = 0
    n = len(s)
    while pos < n:
        if s[pos].isalnum():
            start = pos
            while pos < n and s[pos].isalnum():
                pos += 1
            word = s[start:pos].lower()
            res.append(('word', word))
        else:
            # Consume run of non-alnum (separator)
            while pos < n and not s[pos].isalnum():
                pos += 1
            res.append(('sep', None))
    return res

def input_token_slots(tokens):
    """
    From a list of tokens, classify as ('word', normalized_token) or ('sep', None).
    """
    for tok in tokens:
        if is_word_token(tok):
            yield ('word', normalize_token(tok))
        else:
            yield ('sep', None)

# --- Trie node definition ---

class TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        self.children = {}   # key: ('word', word) or ('sep', None)
        self.entries = set() # dictionary entry ids ending here

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build normalized trie for fast multiword/compound lookup.
    """
    root = TrieNode()

    for phrase, entry_id in dictionary.items():
        slots = dictionary_phrase_slots(phrase)
        node = root
        for slot in slots:
            if slot not in node.children:
                node.children[slot] = TrieNode()
            node = node.children[slot]
        node.entries.add(entry_id)

    # Return both the root and max phrase slot length, for efficient matching window
    def compute_max_depth(node):
        if not node.children:
            return 0
        return 1 + max(compute_max_depth(child) for child in node.children.values())
    maxlen = compute_max_depth(root)
    return {"root": root, "maxlen": maxlen}

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    tokens = list(tokens)
    n = len(tokens)
    trie = dictionary_index["root"]
    maxlen = dictionary_index["maxlen"]

    # Precompute token slots for the input (don't forget to keep original index)
    tok_slots = list(input_token_slots(tokens))

    # Collect for each token: all dictionary entry ids that annotate it
    annotations = [set() for _ in range(n)]

    # For each token as start position
    for start in range(n):
        # Skip matching as start if at a separator token (unless phrases can start with separators, but no test case needs that)
        # However, allow phrase to start at any token to match patterns with leading separator in the dictionary.
        node = trie
        slot_pos = start
        input_pos = start

        # For phrase matching, maintain:
        #   - curr_input: pointer in input
        #   - curr_trie: pointer in trie
        # For each extension, distinguish between extending by word vs sep.
        curr_input = slot_pos
        curr_node = node

        # We'll store (node, input_pos, slot_index_in_phr) on a stack for BFS/DFS.
        # Since sep dictionary slots can match 1 or more consecutive sep tokens in input,
        # we need a little care to handle run of seps.
        stack = []
        stack.append( (curr_node, curr_input, 0, []) ) # (trie node, token pos, phrase slot index, matched input indexes list)
        # phrase slot index is not strictly necessary, just for clarity

        # For each phrase path starting at 'start'
        while stack:
            node, inpos, slotidx, path_indexes = stack.pop()

            # If this is not the first step in the path, and we have reached an end node
            # (meaning we have matched a dictionary entry), record the match
            if node.entries and path_indexes:
                # Annotate tokens in path_indexes except:
                # - skip path_indexes[0] if it's a sep token (leading sep)
                # - skip path_indexes[-1] if it's a sep token (trailing sep)
                indices_to_annotate = path_indexes[:]
                if indices_to_annotate:
                    if not is_word_token(tokens[indices_to_annotate[0]]):
                        indices_to_annotate = indices_to_annotate[1:]
                    if indices_to_annotate and not is_word_token(tokens[indices_to_annotate[-1]]):
                        indices_to_annotate = indices_to_annotate[:-1]
                for idx in indices_to_annotate:
                    annotations[idx].update(node.entries)
            # Stop if reached end of input
            if inpos >= n:
                continue

            # Try extending with the current token as word
            input_slot = tok_slots[inpos]
            if input_slot[0] == "word":
                key = ("word", input_slot[1])
                if key in node.children:
                    stack.append((
                        node.children[key],
                        inpos + 1,
                        slotidx + 1,
                        path_indexes + [inpos]
                    ))

            # Try extending with sep slot(s)
            # A dictionary sep slot can match any run of one or more consecutive sep tokens in input,
            # i.e., ('sep', None) in trie matches consec 'sep' input tokens.
            if ("sep", None) in node.children and input_slot[0] == "sep":
                # Find run (min 1) of consecutive seps starting at inpos
                run_end = inpos
                while run_end < n and tok_slots[run_end][0] == "sep":
                    run_end += 1
                # For each possible run length (at least one sep token), try advancing
                for nextpos in range(inpos + 1, run_end + 1):
                    stack.append((
                        node.children[("sep", None)],
                        nextpos,
                        slotidx + 1,
                        path_indexes + list(range(inpos, nextpos))
                    ))

    # Single-word matches (no phrase, just a standalone word)
    # These *may* have already been found via the above, but in case e.g. the token is not
    # part of any longer phrase, we need to check explicitly.
    # We'll use the trie for this as well (so, not a performance issue).
    node = trie
    for idx, tslot in enumerate(tok_slots):
        if tslot[0] == "word":
            key = ("word", tslot[1])
            node = trie
            if key in node.children:
                node2 = node.children[key]
                if node2.entries:
                    annotations[idx].update(node2.entries)

    # Compose output as per required interface
    annotated_tokens = [ (token, annotations[idx]) for idx, token in enumerate(tokens) ]
    return annotated_tokens
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


