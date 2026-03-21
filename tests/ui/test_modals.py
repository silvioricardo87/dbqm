"""Tests for modal dialogs."""
import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Input, Label

from dbqm.ui.modals.confirm import ConfirmModal
from dbqm.ui.modals.export_picker import ExportPickerModal
from dbqm.ui.modals.param_input import ParamModal
from dbqm.ui.modals.text_input import TextInputModal


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


# --- ConfirmModal tests ---


@pytest.mark.asyncio
async def test_confirm_modal_shows_message():
    modal = ConfirmModal("Remover item?")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ConfirmModal)


@pytest.mark.asyncio
async def test_confirm_modal_esc_returns_false():
    modal = ConfirmModal("Remover?")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("escape")
    assert app.result is False


@pytest.mark.asyncio
async def test_confirm_modal_sim_returns_true():
    modal = ConfirmModal("Remover?")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        btn = app.screen.query_one("#confirm", Button)
        await pilot.click(btn.__class__, offset=(0, 0))
        btn.press()
        await pilot.pause()
    assert app.result is True


@pytest.mark.asyncio
async def test_confirm_modal_nao_returns_false():
    modal = ConfirmModal("Remover?")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        btn = app.screen.query_one("#cancel", Button)
        btn.press()
        await pilot.pause()
    assert app.result is False


# --- TextInputModal tests ---


@pytest.mark.asyncio
async def test_text_input_modal_prefills_default():
    modal = TextInputModal("Novo nome", default="query_1")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inp = app.screen.query(Input).first()
        assert inp.value == "query_1"


@pytest.mark.asyncio
async def test_text_input_modal_esc_returns_none():
    modal = TextInputModal("Nome")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("escape")
    assert app.result is None


@pytest.mark.asyncio
async def test_text_input_modal_enter_returns_value():
    modal = TextInputModal("Nome", default="abc")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("enter")
    assert app.result == "abc"


@pytest.mark.asyncio
async def test_text_input_modal_shows_message():
    modal = TextInputModal("Titulo", message="Digite algo")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, TextInputModal)


# --- ExportPickerModal tests ---


@pytest.mark.asyncio
async def test_export_picker_shows_formats():
    modal = ExportPickerModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, ExportPickerModal)


@pytest.mark.asyncio
async def test_export_picker_esc_returns_none():
    modal = ExportPickerModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("escape")
    assert app.result is None


@pytest.mark.asyncio
async def test_export_picker_has_csv_json_txt():
    modal = ExportPickerModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        buttons = app.screen.query(Button)
        ids = {b.id for b in buttons}
        assert "fmt-csv" in ids
        assert "fmt-json" in ids
        assert "fmt-txt" in ids
        assert "fmt-png" not in ids


@pytest.mark.asyncio
async def test_export_picker_includes_png_when_enabled():
    modal = ExportPickerModal(include_png=True)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        buttons = app.screen.query(Button)
        ids = {b.id for b in buttons}
        assert "fmt-png" in ids


@pytest.mark.asyncio
async def test_export_picker_click_csv_returns_csv():
    modal = ExportPickerModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        btn = app.screen.query_one("#fmt-csv", Button)
        btn.press()
        await pilot.pause()
    assert app.result == "csv"


# --- ParamModal with accented parameter names ---


@pytest.mark.asyncio
async def test_param_modal_accented_names():
    """ParamModal should handle accented parameter names without crashing."""
    params = [
        {"name": "ap\u00f3lice", "description": "N\u00famero da ap\u00f3lice", "default": "12345"},
        {"name": "c\u00f3digo", "description": "C\u00f3digo do cliente", "default": ""},
    ]
    modal = ParamModal("consulta_teste", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        inputs = app.screen.query(Input)
        assert len(inputs) >= 2
        # Should not crash with accented names


@pytest.mark.asyncio
async def test_param_modal_accented_names_submit():
    """ParamModal should return original accented param names on submit."""
    params = [
        {"name": "ap\u00f3lice", "description": "", "default": "999"},
    ]
    modal = ParamModal("test", params)
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("enter")
    assert app.result is not None
    assert "ap\u00f3lice" in app.result
    assert app.result["ap\u00f3lice"] == "999"
