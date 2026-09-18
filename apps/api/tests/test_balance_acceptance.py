from scripts.balance_v34 import statistically_competitive


def outcomes(wins):
    return [{"won": won} for won in wins]


def test_identical_or_better_policies_are_competitive():
    plan = outcomes([True] * 400 + [False] * 100)
    assert statistically_competitive(plan, plan)
    assert statistically_competitive(outcomes([True] * 500), plan)


def test_small_common_seed_differences_do_not_require_an_exact_tie():
    leader = outcomes([True] * 410 + [False] * 90)
    candidate = outcomes([True] * 400 + [False] * 10 + [True] * 8 + [False] * 82)
    assert statistically_competitive(candidate, leader)


def test_materially_weaker_policies_still_fail_the_usefulness_comparison():
    assert not statistically_competitive(
        outcomes([True] * 350 + [False] * 150),
        outcomes([True] * 450 + [False] * 50),
    )
    assert not statistically_competitive(outcomes([False] * 500), outcomes([True] * 500))


def test_a_single_loss_cannot_establish_competitiveness():
    assert not statistically_competitive(outcomes([False]), outcomes([True]))
