#!/usr/bin/env python3

# -----------------
# Реализуйте функцию best_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. У каждой карты есть масть(suit) и
# ранг(rank)
# Масти: трефы(clubs, C), пики(spades, S), червы(hearts, H), бубны(diamonds, D)
# Ранги: 2, 3, 4, 5, 6, 7, 8, 9, 10 (ten, T), валет (jack, J), дама (queen, Q), король (king, K), туз (ace, A)
# Например: AS - туз пик (ace of spades), TH - дестяка черв (ten of hearts), 3C - тройка треф (three of clubs)

# Задание со *
# Реализуйте функцию best_wild_hand, которая принимает на вход
# покерную "руку" (hand) из 7ми карт и возвращает лучшую
# (относительно значения, возвращаемого hand_rank)
# "руку" из 5ти карт. Кроме прочего в данном варианте "рука"
# может включать джокера. Джокеры могут заменить карту любой
# масти и ранга того же цвета, в колоде два джокерва.
# Черный джокер '?B' может быть использован в качестве треф
# или пик любого ранга, красный джокер '?R' - в качестве черв и бубен
# любого ранга.

# Одна функция уже реализована, сигнатуры и описания других даны.
# Вам наверняка пригодится itertools
# Можно свободно определять свои функции и т.п.
# -----------------

import itertools

from collections import Counter


RANK_MAP = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
    "9": 9, "10": 10, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
}

RED_JOKER = "?R"
BLACK_JOKER = "?B"

CARDS_IN_HAND = 5
STRAIGHT_CARDS_COUNT = CARDS_IN_HAND

WHEEL = [14, 5, 4, 3, 2]
WHEEL_RANKS = [5, 4, 3, 2, 1]


def hand_rank(hand):
    """Возвращает значение определяющее ранг 'руки'"""
    ranks = card_ranks(hand)
    if straight(ranks) and flush(hand):
        return (8, max(ranks))
    elif kind(4, ranks):
        return (7, kind(4, ranks), kind(1, ranks))
    elif kind(3, ranks) and kind(2, ranks):
        return (6, kind(3, ranks), kind(2, ranks))
    elif flush(hand):
        return (5, ranks)
    elif straight(ranks):
        return (4, max(ranks))
    elif kind(3, ranks):
        return (3, kind(3, ranks), ranks)
    elif two_pair(ranks):
        return (2, two_pair(ranks), ranks)
    elif kind(2, ranks):
        return (1, kind(2, ranks), ranks)
    else:
        return (0, ranks)


def card_ranks(hand):
    """Возвращает список рангов (его числовой эквивалент),
    отсортированный от большего к меньшему"""
    ranks = sorted((RANK_MAP[card[:-1]] for card in hand), reverse=True)
    if ranks == WHEEL:
        return WHEEL_RANKS
    return ranks


def flush(hand):
    """Возвращает True, если все карты одной масти"""
    # same result: len(set(card[1] for card in hand)) <= 1
    g = itertools.groupby(hand, key=lambda card: card[1])
    return next(g, True) and not next(g, False)


def straight(ranks):
    """Возвращает True, если отсортированные ранги формируют последовательность 5ти,
    где у 5ти карт ранги идут по порядку (стрит)"""
    if len(set(ranks)) < STRAIGHT_CARDS_COUNT:
        return False

    iterators = itertools.tee(ranks)
    for count, iterator in enumerate(iterators):
        [next(iterator) for _ in range(count)]
    return all(first - second == 1 for first, second in zip(*iterators))


def kind(n, ranks):
    """Возвращает первый ранг, который n раз встречается в данной руке.
    Возвращает None, если ничего не найдено"""
    counts = Counter(ranks)
    sorted_counts = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
    first = next(filter(lambda count_item: count_item[0] == n, sorted_counts), None)
    if first is None:
        return
    # first is (count, rank)
    return first[1]


def two_pair(ranks):
    """Если есть две пары, то возврщает два соответствующих ранга,
    иначе возвращает None"""
    result = list(pair[0] for pair in filter(lambda pair: pair[0] == pair[1], itertools.combinations(ranks, 2)))
    if len(result) < 2:
        return None

    result.sort(reverse=True)
    return result[:2]


def best_hand(hand):
    """Из "руки" в 7 карт возвращает лучшую "руку" в 5 карт """
    hand_combinations = itertools.combinations(hand, 5)
    return max(hand_combinations, key=hand_rank)


def best_wild_hand(hand):
    """best_hand но с джокерами"""
    jokers_in_hand = list(filter(lambda card: "?" in card, hand))
    ranks = list(filter(lambda rank: rank != "10", RANK_MAP.keys()))

    black_joker_cards = None
    red_joker_cards = None
    for joker in jokers_in_hand:
        if joker == BLACK_JOKER:
            black_joker_cards = ("".join([rank, suit]) for rank, suit in itertools.product(ranks, "CS"))
            black_joker_cards = filter(lambda card: card not in hand, black_joker_cards)
            black_joker_cards = ((card,) for card in black_joker_cards)
        if joker == RED_JOKER:
            red_joker_cards = ("".join([rank, suit]) for rank, suit in itertools.product(ranks, "HD"))
            red_joker_cards = filter(lambda card: card not in hand, red_joker_cards)
            red_joker_cards = ((card,) for card in red_joker_cards)
        hand.remove(joker)

    hand_general_comb = itertools.combinations(hand, CARDS_IN_HAND)
    hand_combinations = []

    hand_without_joker = itertools.combinations(hand, CARDS_IN_HAND - len(jokers_in_hand))
    if black_joker_cards is not None and red_joker_cards is not None:
        hand_combinations = itertools.product(hand_without_joker, black_joker_cards, red_joker_cards)
    elif black_joker_cards is not None:
        hand_combinations = itertools.product(hand_without_joker, black_joker_cards)
    elif red_joker_cards is not None:
        hand_combinations = itertools.product(hand_without_joker, red_joker_cards)

    hand_combinations = (flatten(combination) for combination in hand_combinations)
    return max(itertools.chain(hand_general_comb, hand_combinations), key=hand_rank)


def flatten(iterable):
    iterators = map(lambda item: item if hasattr(item, "__iter__") else (item, ), iterable)
    return list(itertools.chain.from_iterable(iterators))


def test_two_pair():
    print("test_two_pair...")
    assert (two_pair([]) is None)
    assert (two_pair([8, 7, 6, 5]) is None)
    assert (two_pair([8, 7, 6, 5, 5]) is None)
    assert (two_pair([8, 7, 6, 6, 5, 5]) == [6, 5])
    print('OK')


def test_kind():
    print("test_kind...")
    assert (kind(3, [9, 8, 7, 7, 5, 5, 5, 4, 4, 4]) == 5)
    assert (kind(3, [9, 8, 7, 7, 5, 5, 4, 4]) is None)
    assert (kind(3, []) is None)
    print('OK')


def test_flatten():
    print("test_flatten...")
    assert (flatten([[1, 2], 3, 4]) == [1, 2, 3, 4])
    assert (flatten([[1, 2], 3, 4, [5, 6]]) == [1, 2, 3, 4, 5, 6])
    assert (flatten([]) == [])
    print('OK')


def test_straight():
    print("test_straight...")
    assert (straight([]) is False)
    assert (straight([8, 7, 6, 5]) is False)
    assert (straight([10, 7, 6, 5, 5]) is False)
    assert (straight([8, 7, 6, 5, 4]) is True)
    print('OK')


def test_card_ranks():
    print("test_card_ranks...")
    assert (card_ranks(["6C", "7D", "9C"]) == [9, 7, 6])
    assert (card_ranks(["6C", "KD", "AC"]) == [14, 13, 6])
    assert (card_ranks([]) == [])
    print('OK')


def test_flush():
    print("test_flush...")
    assert (flush([]) is True)
    assert (flush(["6C", "7C", "8C"]) is True)
    assert (flush(["6C", "7D"]) is False)
    print('OK')


def test_best_hand():
    print("test_best_hand...")
    assert (sorted(best_hand("6C 7C 8C 9C TC 5C JS".split()))
            == ['6C', '7C', '8C', '9C', 'TC'])
    assert (sorted(best_hand("TD TC TH 7C 7D 8C 8S".split()))
            == ['8C', '8S', 'TC', 'TD', 'TH'])
    assert (sorted(best_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


def test_best_wild_hand():
    print("test_best_wild_hand...")
    assert (sorted(best_wild_hand("6C 7C 8C 9C TC 5C ?B".split()))
            == ['7C', '8C', '9C', 'JC', 'TC'])
    assert (sorted(best_wild_hand("TD TC 5H 5C 7C ?R ?B".split()))
            == ['7C', 'TC', 'TD', 'TH', 'TS'])
    assert (sorted(best_wild_hand("JD TC TH 7C 7D 7S 7H".split()))
            == ['7C', '7D', '7H', '7S', 'JD'])
    print('OK')


if __name__ == '__main__':
    test_flush()
    test_card_ranks()
    test_straight()
    test_kind()
    test_two_pair()
    test_flatten()
    test_best_hand()
    test_best_wild_hand()
