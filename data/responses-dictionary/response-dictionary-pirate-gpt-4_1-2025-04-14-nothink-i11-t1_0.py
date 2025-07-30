# --- BEGIN GENERATED CODE ---
import collections.abc

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie index from the dictionary for fast phrase matching.
    """

    # Helper: split a phrase into lowercased word(-ish) tokens
    def tokenize_phrase(phrase):
        # We'll treat splits on spaces, commas, and other whitespace/obvious separators
        # Dict entries may have separators or not. For simplicity, split on space/comma
        # and treat result as the sequence
        tokens = []
        buf = ""
        for c in phrase:
            if c.isalnum() or c in ("_", "'"):  # Word building
                buf += c
            else:
                if buf:
                    tokens.append(buf)
                    buf = ""
                # Treat groups of separator chars (space, comma) as one
                if c.strip() != "":
                    tokens.append(c)
                elif tokens and tokens[-1] != " ":
                    tokens.append(" ")
        if buf:
            tokens.append(buf)
        # Remove empty separators
        return [t.lower() for t in tokens if t.strip() or t.isalnum()]
    
    # Trie node: dict of next-token -> child, plus set of dictionary ids for ends
    class TrieNode:
        def __init__(self):
            self.children = dict()
            self.ids = set()
    
    # Root of trie
    trie_root = TrieNode()
    max_phrase_len = 1
    # Flat word dict for single-word lookup
    word_dict = dict()
    
    for phrase, id_ in dictionary.items():
        # For trie, split on spaces and commas, but treat all as case-insensitive
        # We'll support separators in phrase as well, so the phrase can be "foo bar" or "foo, bar"
        # For single-word dict, map normalized word to its ids (allowing multiple ids per word)
        norm_phrase = phrase.lower()
        words = []
        # Split phrase on spaces and keep nonspace chars as separators
        prev_was_word = False
        temp = ""
        for c in norm_phrase:
            if c.isalnum() or c in ("_", "'"):
                temp += c
                prev_was_word = True
            else:
                if temp:
                    words.append(temp)
                    temp = ""
                if c.strip():  # non-whitespace separators (like commas)
                    words.append(c)
                elif prev_was_word:
                    words.append(" ")
                    prev_was_word = False
        if temp:
            words.append(temp)
        # Mash up: skip empty separators at ends
        while words and not words[0].isalnum() and not words[0] == "'":
            words.pop(0)
        while words and not words[-1].isalnum() and not words[-1] == "'":
            words.pop()
        # Single-word dict
        if len(words) == 1 and (words[0].isalnum() or words[0] == "'"):
            if words[0] not in word_dict:
                word_dict[words[0]] = set()
            word_dict[words[0]].add(id_)
        # Trie insert
        node = trie_root
        for w in words:
            if w not in node.children:
                node.children[w] = TrieNode()
            node = node.children[w]
        node.ids.add(id_)
        max_phrase_len = max(max_phrase_len, len(words))
    
    # We'll also need to know if a token is a word
    def is_word(token):
        return any(c.isalnum() for c in token)
    
    return {
        "trie_root": trie_root,
        "word_dict": word_dict,
        "maxlen": max_phrase_len,
        "is_word": is_word,
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary, supportin' words and compound phrases.
    """
    trie_root = dictionary_index["trie_root"]
    word_dict = dictionary_index["word_dict"]
    max_phrase_len = dictionary_index["maxlen"]
    is_word = dictionary_index["is_word"]

    annots = [set() for _ in tokens]
    tokens = list(tokens)  # To allow multiple passes and indexing

    N = len(tokens)
    # single-word matching
    for i, tok in enumerate(tokens):
        tok_norm = tok.lower()
        if is_word(tok_norm):
            if tok_norm in word_dict:
                annots[i].update(word_dict[tok_norm])

    # phrase-matching
    # For every start position, if it is a word, try to match
    for start in range(N):
        # Only try to start phrase at a word token
        if not is_word(tokens[start]):
            continue
        ends = []  # will collect (end, ids) tuples for finished phrases
        node = trie_root
        # Record indices of word tokens; for phrase matching we must know their places
        word_token_indices = []
        j = start
        steps = 0
        while j < N and steps < max_phrase_len:
            tok_norm = tokens[j].lower()
            if is_word(tokens[j]):
                word_token_indices.append(j)
                key = tok_norm
            else:
                key = tokens[j]
            if key not in node.children:
                break
            node = node.children[key]
            if node.ids:
                # Save: match runs from start to j (inclusive)
                # We'll annotate *inner* separators only, never leading or trailing!
                ends.append((j, node.ids))
            j += 1
            steps += 1
        # For each phrase match found, annotate all tokens in the span:
        for end, ids in ends:
            # To annotate only the inner separators:
            # First and last word-token in this substring:
            word_idxs = [idx for idx in range(start, end + 1) if is_word(tokens[idx])]
            if not word_idxs:
                continue  # Defensive
            first_word = word_idxs[0]
            last_word = word_idxs[-1]
            for idx in range(start, end + 1):
                if is_word(tokens[idx]):
                    annots[idx].update(ids)
                else:
                    # Separator: only annotate if strictly between first+last word
                    if first_word < idx < last_word:
                        annots[idx].update(ids)
    # Create output tuples
    annotated_tokens = [(t, annots[i]) for i, t in enumerate(tokens)]
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


