import pytest
@pytest.mark.parametrize("n,exp",[(2,4),(3,6)])
def test_double(n,exp):
    assert double(n)==exp
