# --- BEGIN GENERATED CODE ---
import collections.abc

def _normalize_token(s):
    """Normalize token for comparison (currently: case insensitive)."""
    return s.lower()

def _is_word(token):
    # Heuristic: Word tokens contain at least one alpha or digit.
    return any(c.isalnum() for c in token)

def _tokenize_phrase(phrase_str):
    """
    Tokenize a dictionary phrase string into word/separator tokens.
    For the dictionary, treat any sequence of non-alnum chars as separate tokens.
    """
    # Simplest built-in split: Use runs of alnum/non-alnum as tokens.
    tokens = []
    acc = ''
    is_word = None
    for c in phrase_str:
        c_is_word = c.isalnum()
        if is_word is None:
            acc = c
            is_word = c_is_word
        elif c_is_word == is_word:
            acc += c
        else:
            tokens.append(acc)
            acc = c
            is_word = c_is_word
    if acc:
        tokens.append(acc)
    return tokens

class _PhraseTrieNode:
    __slots__ = ('children', 'end_ids')
    def __init__(self):
        # children: mapping normalized token or None (separator slot) to child node
        self.children = {}
        self.end_ids = set()  # set of dictionary ids for phrases/words ending here

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.
    """
    # Single-word lookup: normalized token -> set(ids)
    word_index = collections.defaultdict(set)
    # Root of phrase trie
    phrase_root = _PhraseTrieNode()
    # For remembering the lengths of each phrase by id for later
    phrase_id_to_length = {}

    for phrase, id_ in dictionary.items():
        tokens = _tokenize_phrase(phrase)
        norm_tokens = []
        # For phrase matching, treat word tokens as normalized, separator slots as None
        for tok in tokens:
            if _is_word(tok):
                norm_tokens.append(_normalize_token(tok))
            else:
                norm_tokens.append(None)  # Special marker for a separator slot

        # Compact consecutive None (multiple separators in a row) into a single None
        compacted = []
        for t in norm_tokens:
            if t is None and compacted and compacted[-1] is None:
                continue
            compacted.append(t)
        norm_tokens = compacted

        # For 1-word phrases (no separators), fill in word_index for fast lookup
        if all(t is not None for t in norm_tokens):
            # Join if more than one? Single-token? See test_compound_word_tokens_missing_from_dictionary.
            # A dictionary entry 'AAABBB' → single token 'AAABBB', not split.
            if len(norm_tokens) == 1:
                word_index[norm_tokens[0]].add(id_)
            # compound word (like German 'Lebensversicherungsgesellschaftsangestellter'), still treat as phrase
        else:
            # Could also be a multi-word or phrase
            # For every phrase (word or multi-word), insert into phrase trie
            node = phrase_root
            for t in norm_tokens:
                if t not in node.children:
                    node.children[t] = _PhraseTrieNode()
                node = node.children[t]
            node.end_ids.add(id_)
            phrase_id_to_length[id_] = len(norm_tokens)
        # But also, for, say, 'black swan' (["black", None, "swan"]), we want to catch "black" and "swan" as single-word entries too (see test_compound_phrase_and_individual_word)
        # So, for any phrase, if it's a single word token, always in word_index as well (already above).

    return {
        'word_index': word_index,
        'phrase_root': phrase_root,
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.
    """
    tokens = list(tokens)
    L = len(tokens)
    annotations = [set() for _ in tokens]

    word_index = dictionary_index['word_index']
    phrase_root = dictionary_index['phrase_root']

    # --- PHRASE MATCHING ---
    # We want to match all possible phrases (including those overlapping)
    norm_tokens = [_normalize_token(t) if _is_word(t) else None for t in tokens]
    # At every position, try to traverse the trie as far as possible, matching phrases
    for start in range(L):
        trie_node = phrase_root
        token_pos = start
        trie_depth = 0
        while token_pos < L:
            ntok = norm_tokens[token_pos]
            # First, try word branch
            if ntok is not None and ntok in trie_node.children:
                trie_node = trie_node.children[ntok]
                trie_depth += 1
                if trie_node.end_ids:
                    # Phrase match found
                    # Figure out which tokens to annotate
                    # (Leading and trailing separators excluded)
                    # Find phrase span for annotation: from start to token_pos, inclusive
                    # But skip leading separators: [start, ...] if token is separator and is the first token in phrase
                    left = start
                    right = token_pos
                    # Remove leading/trailing separators when annotating
                    # That is, if tokens[left] is separator, and left == start, skip it for annotation.
                    # But for inner separators, include.
                    # Likewise for trailing.
                    # Only annotate separators inside the matched phrase, not ones at very start or very end.
                    # But this check should correspond to the positions progressed by the trie.

                    # Head
                    while left < right and norm_tokens[left] is None:
                        left += 1
                    # Tail
                    while right > left and norm_tokens[right] is None:
                        right -= 1
                    # Annotate all tokens from left to right, inclusive
                    for pos in range(left, right + 1):
                        annotations[pos].update(trie_node.end_ids)
                token_pos += 1
            # Next, try separator slot (None in trie) if current token is a separator
            elif ntok is None and None in trie_node.children:
                # Allow one or more consecutive separator tokens to match single separator slot
                sep_pos = token_pos
                # For matching purposes, treat consecutive separators as one None slot in the trie
                while sep_pos < L and norm_tokens[sep_pos] is None:
                    sep_pos += 1
                trie_node = trie_node.children[None]
                trie_depth += 1
                token_pos = sep_pos  # move past all separator tokens
                if token_pos > L:
                    break
                if trie_node.end_ids and token_pos > 0: # phrase can end here even after separator
                    # Annotate as above
                    left = start
                    right = token_pos - 1
                    while left < right and norm_tokens[left] is None:
                        left += 1
                    while right > left and norm_tokens[right] is None:
                        right -= 1
                    for pos in range(left, right + 1):
                        annotations[pos].update(trie_node.end_ids)
            else:
                break

    # --- SINGLE TOKEN WORDS ---
    for i, (tok, ntok) in enumerate(zip(tokens, norm_tokens)):
        if ntok is not None and ntok in word_index:
            annotations[i].update(word_index[ntok])

    # Output in required format
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


