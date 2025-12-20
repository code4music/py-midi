from flask import Flask, jsonify, request, render_template
from .utils import log


def create_app(synth):
    app = Flask(__name__, template_folder="templates")

    @app.route('/')
    def index():
        instruments = {
            name: {
                "file": inst["sf"],
                "channel": inst.get("channel", 0),
                "bank": inst.get("bank", 0),
                "preset": inst.get("preset", 0),
                "preset_name": inst.get("preset_name", "None"),
            }
            for name, inst in synth.instruments.items()
        }

        banks = synth.cfg.list_banks()
        active_bank = synth.cfg.get_active_bank() or "(nenhum)"
        
        return render_template("index.html", 
                             instruments=instruments,
                             banks=banks,
                             active_bank=active_bank)

    @app.route('/banks')
    def list_banks():
        """Lista todos os banks disponíveis"""
        return jsonify(synth.cfg.list_banks())

    @app.route('/switch_bank', methods=['POST'])
    def switch_bank():
        """Troca o banco ativo"""
        data = request.json or {}
        bank_name = data.get('bank')
        
        if synth.switch_bank(bank_name):
            instruments = {
                name: {
                    "file": inst["sf"],
                    "channel": inst.get("channel", 0),
                    "volume": inst.get("volume", 0),
                    "preset_name": inst.get("preset_name", "None"),
                }
                for name, inst in synth.instruments.items()
            }
            return jsonify({"ok": True, "instruments": instruments})
        else:
            return jsonify({"ok": False, "error": "Bank not found"}), 404

    @app.route('/panic', methods=['POST'])
    def panic():
        """Para todos os sons imediatamente"""
        synth.panic()
        return jsonify({"ok": True})

    @app.route('/presets/<inst>')
    def list_presets(inst):
        return jsonify(synth.list_presets(inst))


    @app.route('/set_preset', methods=['POST'])
    def set_preset_route():
        payload = request.json or {}
        name = payload.get("instrument")
        preset_number = int(payload.get("preset", 0))

        synth.set_preset(name, preset_number)

        preset_list = synth.list_presets(name)
        preset_entry = next((p for p in preset_list if p["preset"] == preset_number), None)
        preset_name = preset_entry["name"] if preset_entry else "Desconhecido"

        inst = synth.instruments.get(name)
        if inst:
            inst["preset"] = preset_number
            inst["preset_name"] = preset_name

        return jsonify({
            "ok": True,
            "preset_name": preset_name
        })

    @app.route('/set_volume', methods=['POST'])
    def set_volume():
        data = request.json or {}
        name = data.get('name')
        value = data.get('value')
        synth.set_instrument_volume(name, int(value))
        return jsonify({"ok": True})

    return app
