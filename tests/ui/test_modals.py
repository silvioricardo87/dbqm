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


# --- ExportDirSetupModal ---


@pytest.mark.asyncio
async def test_export_dir_setup_starts_with_cwd_checked():
    """Default state: 'usar diretorio atual' is on, input is disabled."""
    from textual.widgets import Checkbox
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

    modal = ExportDirSetupModal()
    app = ModalTestApp(modal)
    async with app.run_test():
        checkbox = app.screen.query_one("#use-cwd-checkbox", Checkbox)
        path_input = app.screen.query_one("#export-dir-input", Input)
        assert checkbox.value is True
        assert path_input.disabled is True


@pytest.mark.asyncio
async def test_export_dir_setup_unchecking_enables_input():
    """Unchecking the 'use cwd' checkbox must enable the path input."""
    from textual.widgets import Checkbox
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

    modal = ExportDirSetupModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        checkbox = app.screen.query_one("#use-cwd-checkbox", Checkbox)
        checkbox.value = False
        await pilot.pause()
        path_input = app.screen.query_one("#export-dir-input", Input)
        assert path_input.disabled is False


@pytest.mark.asyncio
async def test_export_dir_setup_rejects_nonexistent_path(tmp_config_dir):
    """Saving a path that does not exist must surface an error and not dismiss."""
    from textual.widgets import Button, Checkbox
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

    modal = ExportDirSetupModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        app.screen.query_one("#use-cwd-checkbox", Checkbox).value = False
        await pilot.pause()
        app.screen.query_one("#export-dir-input", Input).value = "Z:/does/not/exist/xyz"
        await pilot.pause()
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        # Modal must still be open \u2014 no dismiss yet.
        assert isinstance(app.screen, ExportDirSetupModal)
    assert app.result is None


@pytest.mark.asyncio
async def test_export_dir_setup_saves_valid_path(tmp_config_dir):
    """A valid path saves settings and dismisses with True."""
    from textual.widgets import Button, Checkbox
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal
    from dbqm.models.settings import load_settings

    target = tmp_config_dir / "custom"
    target.mkdir()

    modal = ExportDirSetupModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        app.screen.query_one("#use-cwd-checkbox", Checkbox).value = False
        await pilot.pause()
        app.screen.query_one("#export-dir-input", Input).value = str(target)
        await pilot.pause()
        app.screen.query_one("#save", Button).press()
        await pilot.pause()

    assert app.result is True
    settings = load_settings()
    assert settings.default_export_dir == str(target)
    assert settings.export_dir_prompted is True


@pytest.mark.asyncio
async def test_export_dir_setup_saves_cwd_choice(tmp_config_dir):
    """Saving with the checkbox ON clears default_export_dir and marks prompted."""
    from textual.widgets import Button
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal
    from dbqm.models.settings import Settings, save_settings, load_settings

    # Pre-existing custom dir; user now switches back to cwd.
    save_settings(Settings(default_export_dir="/old/path", export_dir_prompted=True))

    modal = ExportDirSetupModal(initial_use_cwd=True, initial_path="")
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        app.screen.query_one("#save", Button).press()
        await pilot.pause()

    assert app.result is True
    settings = load_settings()
    assert settings.default_export_dir == ""
    assert settings.export_dir_prompted is True


@pytest.mark.asyncio
async def test_export_dir_setup_cancel_does_not_persist(tmp_config_dir):
    """Cancel must not touch settings \u2014 the prompt should fire again next time."""
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal
    from dbqm.models.settings import load_settings

    modal = ExportDirSetupModal()
    app = ModalTestApp(modal)
    async with app.run_test() as pilot:
        await pilot.press("escape")
    assert app.result is False
    settings = load_settings()
    assert settings.export_dir_prompted is False


# --- request_export orchestration ---


@pytest.mark.asyncio
async def test_request_export_shows_setup_first_when_not_prompted(tmp_config_dir):
    """First export ever: setup modal appears before the format picker."""
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal
    from dbqm.ui.modals.export_picker import request_export
    from dbqm.models.settings import Settings, save_settings

    save_settings(Settings(export_dir_prompted=False))

    class _App(App):
        def on_mount(self):
            request_export(self, callback=lambda fmt: None)

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ExportDirSetupModal)


@pytest.mark.asyncio
async def test_request_export_skips_setup_after_prompted(tmp_config_dir):
    """Once the user has been prompted, the format picker opens directly."""
    from dbqm.ui.modals.export_picker import ExportPickerModal, request_export
    from dbqm.models.settings import Settings, save_settings

    save_settings(Settings(export_dir_prompted=True))

    class _App(App):
        def on_mount(self):
            request_export(self, callback=lambda fmt: None)

    app = _App()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ExportPickerModal)


# --- OracleClientDirModal ---


def _fake_client(base, name="instantclient_19_x64"):
    """Create a client directory whose oci.dll matches the running Python."""
    import struct
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    machine = 0x8664 if struct.calcsize("P") * 8 == 64 else 0x014C
    pe_offset = 0x80
    buf = bytearray(pe_offset + 8)
    buf[0:2] = b"MZ"
    buf[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    buf[pe_offset:pe_offset + 4] = b"PE\x00\x00"
    buf[pe_offset + 4:pe_offset + 6] = machine.to_bytes(2, "little")
    (d / "oci.dll").write_bytes(bytes(buf))
    return d


@pytest.mark.asyncio
async def test_oracle_client_dir_modal_starts_in_auto_mode(tmp_config_dir):
    """With nothing configured, auto-detect is checked and the input disabled."""
    from textual.widgets import Checkbox
    from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

    app = ModalTestApp(OracleClientDirModal())
    async with app.run_test():
        assert app.screen.query_one("#use-auto-checkbox", Checkbox).value is True
        assert app.screen.query_one("#oracle-client-dir-input", Input).disabled is True


@pytest.mark.asyncio
async def test_oracle_client_dir_modal_rejects_invalid_dir(tmp_config_dir):
    """An unusable path keeps the modal open and persists nothing."""
    from textual.widgets import Button, Checkbox
    from dbqm.models.settings import load_settings
    from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

    app = ModalTestApp(OracleClientDirModal())
    async with app.run_test() as pilot:
        app.screen.query_one("#use-auto-checkbox", Checkbox).value = False
        await pilot.pause()
        app.screen.query_one("#oracle-client-dir-input", Input).value = "Z:/nope/xyz"
        await pilot.pause()
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, OracleClientDirModal)
    assert load_settings().oracle_client_dir == ""


@pytest.mark.asyncio
async def test_oracle_client_dir_modal_saves_valid_client(tmp_config_dir):
    from textual.widgets import Button, Checkbox
    from dbqm.models.settings import load_settings
    from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

    client = _fake_client(tmp_config_dir)
    app = ModalTestApp(OracleClientDirModal())
    async with app.run_test() as pilot:
        app.screen.query_one("#use-auto-checkbox", Checkbox).value = False
        await pilot.pause()
        app.screen.query_one("#oracle-client-dir-input", Input).value = str(client)
        await pilot.pause()
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
    assert app.result is True
    assert load_settings().oracle_client_dir == str(client)


@pytest.mark.asyncio
async def test_oracle_client_dir_modal_auto_mode_clears_configured_path(tmp_config_dir):
    """Re-checking auto-detect wipes the stored path."""
    from textual.widgets import Button
    from dbqm.models.settings import Settings, load_settings, save_settings
    from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

    client = _fake_client(tmp_config_dir)
    save_settings(Settings(oracle_client_dir=str(client)))

    app = ModalTestApp(OracleClientDirModal(initial_path=str(client)))
    async with app.run_test() as pilot:
        from textual.widgets import Checkbox
        assert app.screen.query_one("#use-auto-checkbox", Checkbox).value is False
        app.screen.query_one("#use-auto-checkbox", Checkbox).value = True
        await pilot.pause()
        app.screen.query_one("#save", Button).press()
        await pilot.pause()
    assert app.result is True
    assert load_settings().oracle_client_dir == ""
