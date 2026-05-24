"""Unit tests for position state machine."""
import pytest
from unittest.mock import MagicMock
from src.core.exceptions import InvalidPositionTransitionError
from src.positions.tracker import transition, open_position, begin_close, finalize_close
from src.core.enums import PositionStatus, ExitReason


def _mock_position(status="pending"):
    p = MagicMock()
    p.status = status
    p.id = 1
    return p


class TestPositionTransitions:
    def test_pending_to_open(self):
        pos = _mock_position("pending")
        log = open_position(pos)
        assert pos.status == PositionStatus.OPEN.value

    def test_open_to_closing(self):
        pos = _mock_position("open")
        log = begin_close(pos, ExitReason.MANUAL)
        assert pos.status == PositionStatus.CLOSING.value

    def test_closing_to_closed(self):
        pos = _mock_position("closing")
        log = finalize_close(pos, exit_price=0.8, realized_pnl=3.0)
        assert pos.status == PositionStatus.CLOSED.value

    def test_invalid_transition_raises(self):
        pos = _mock_position("closed")
        with pytest.raises(InvalidPositionTransitionError):
            open_position(pos)

    def test_pending_to_closed_invalid(self):
        pos = _mock_position("pending")
        with pytest.raises(InvalidPositionTransitionError):
            finalize_close(pos, 0.5, 0.0)
