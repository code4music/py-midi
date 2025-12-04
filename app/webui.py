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
        return render_template("index.html", instruments=instruments)

    @app.route('/presets/<inst>')
    def list_presets(inst):
        return jsonify(synth.list_presets(inst))


    @app.route('/set_preset', methods=['POST'])
    def set_preset_route():
        payload = request.json or {}
        name = payload.get("instrument")
        preset_number = int(payload.get("preset", 0))

        synth.set_preset(name, preset_number)

        preset_list = synth.list_presets(name)   # agora retorna ints
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
