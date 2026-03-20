"""Tests for modal dialogs."""
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Label

from dbqm.ui.modals.param_input import ParamModal


class ModalTestApp(App):
    result = None

    def __init__(self, modal):
        super().__init__()
        self._modal = modal

    def on_mount(self):
        def on_dismiss(value):
            self.result = value
            self.exit()

        self.push_screen(self._modal, callback=on_dismiss)


@pytest.mark.asyncio
async def test_param_modal_shows_fields():
    params = [
        {"name": "apolice", "description": "Numero da apolice", "default": ""},
        {"name": "dt_ref", "description": "Data referencia", "default": "2024-01-15"},
    ]
    modal = ParamModal("saldo_cliente", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inputs = app.screen.query(Input)
        assert len(inputs) >= 2


@pytest.mark.asyncio
async def test_param_modal_prefills_defaults():
    params = [
        {"name": "dt_ref", "description": "", "default": "2024-01-15"},
    ]
    modal = ParamModal("test", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inp = app.screen.query(Input).first()
        assert inp.value == "2024-01-15"


@pytest.mark.asyncio
async def test_param_modal_prefills_last_values():
    params = [
        {"name": "apolice", "description": "", "default": ""},
    ]
    modal = ParamModal("test", params, last_values={"apolice": "999"})
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inp = app.screen.query(Input).first()
        assert inp.value == "999"


@pytest.mark.asyncio
async def test_param_modal_last_values_override_defaults():
    """Last-used values should take precedence over defaults."""
    params = [
        {"name": "dt_ref", "description": "", "default": "2024-01-15"},
    ]
    modal = ParamModal("test", params, last_values={"dt_ref": "2025-06-01"})
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inp = app.screen.query(Input).first()
        assert inp.value == "2025-06-01"


@pytest.mark.asyncio
async def test_param_modal_cancel_returns_none():
    """Pressing ESC should dismiss with None."""
    params = [
        {"name": "apolice", "description": "", "default": ""},
    ]
    modal = ParamModal("test", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("escape")
        assert app.result is None


@pytest.mark.asyncio
async def test_param_modal_submit_returns_dict():
    """Pressing Enter on last field should return collected values."""
    params = [
        {"name": "apolice", "description": "", "default": "123"},
    ]
    modal = ParamModal("test", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("enter")
        assert app.result == {"apolice": "123"}


@pytest.mark.asyncio
async def test_param_modal_shows_description_subtitle():
    """Description should appear as subtitle when provided."""
    params = [{"name": "x", "description": "", "default": ""}]
    modal = ParamModal("test", params, description="My query description")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        subtitle = app.screen.query_one("#subtitle")
        assert "My query description" in subtitle.render().plain


@pytest.mark.asyncio
async def test_param_modal_label_format():
    """Labels should show :param_name (description) format."""
    params = [
        {"name": "apolice", "description": "Numero da apolice", "default": ""},
    ]
    modal = ParamModal("test", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        labels = [l for l in app.screen.query(Label) if "param-label" in l.classes]
        assert len(labels) == 1
        text = labels[0].render().plain
        assert ":apolice" in text
        assert "(Numero da apolice)" in text
