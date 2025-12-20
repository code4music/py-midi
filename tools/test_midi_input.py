#!/usr/bin/env python3
"""
Script simples para testar entrada MIDI e descobrir controles.
Use este script para ver TODAS as mensagens MIDI que chegam.
"""

import rtmidi
import time

def main():
    midi_in = rtmidi.MidiIn()
    ports = midi_in.get_ports()
    
    print("=" * 60)
    print("🎹 TESTE DE ENTRADA MIDI - Roland XPS-30")
    print("=" * 60)
    print("\nPortas MIDI disponíveis:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port}")
    
    if not ports:
        print("\n❌ Nenhuma porta MIDI encontrada!")
        print("   Conecte seu Roland XPS-30 via USB e tente novamente.")
        return
    
    # Abre todas as portas
    midi_inputs = []
    for i in range(len(ports)):
        try:
            mi = rtmidi.MidiIn()
            mi.open_port(i)
            midi_inputs.append((i, ports[i], mi))
            print(f"\n✅ Porta {i} aberta: {ports[i]}")
        except Exception as e:
            print(f"\n⚠️  Erro ao abrir porta {i}: {e}")
    
    if not midi_inputs:
        print("\n❌ Não foi possível abrir nenhuma porta!")
        return
    
    print("\n" + "=" * 60)
    print("🎛️  MOVA OS KNOBS, SLIDERS E BOTÕES DO SEU TECLADO")
    print("=" * 60)
    print("\nAguardando mensagens MIDI... (Ctrl+C para sair)\n")
    
    last_cc = {}  # Rastreia último valor de cada CC para evitar spam
    
    try:
        while True:
            for port_idx, port_name, midi in midi_inputs:
                msg = midi.get_message()
                if not msg:
                    continue
                
                data, delta = msg
                status = data[0] & 0xF0
                channel = data[0] & 0x0F
                
                # Note On
                if status == 0x90 and len(data) >= 3 and data[2] > 0:
                    print(f"🎵 NOTE ON  - Porta: {port_idx} | Canal: {channel} | "
                          f"Nota: {data[1]} | Velocity: {data[2]}")
                
                # Note Off
                elif status == 0x80 or (status == 0x90 and len(data) >= 3 and data[2] == 0):
                    print(f"🎵 NOTE OFF - Porta: {port_idx} | Canal: {channel} | Nota: {data[1]}")
                
                # Control Change (KNOBS/SLIDERS)
                elif status == 0xB0 and len(data) >= 3:
                    cc_num = data[1]
                    cc_val = data[2]
                    key = f"{port_idx}_{channel}_{cc_num}"
                    
                    # Só mostra se valor mudou (evita spam)
                    if key not in last_cc or last_cc[key] != cc_val:
                        last_cc[key] = cc_val
                        print(f"🎛️  CC#{cc_num:3d} = {cc_val:3d}  | "
                              f"Porta: {port_idx} | Canal: {channel} | "
                              f"📝 Adicione: {cc_num}: \"NomeInstrumento\"")
                
                # Program Change
                elif status == 0xC0 and len(data) >= 2:
                    print(f"🎹 PROGRAM CHANGE - Porta: {port_idx} | "
                          f"Canal: {channel} | Program: {data[1]}")
                
                # Pitch Bend
                elif status == 0xE0 and len(data) >= 3:
                    value = data[1] + (data[2] << 7)
                    print(f"🎚️  PITCH BEND - Porta: {port_idx} | "
                          f"Canal: {channel} | Valor: {value}")
                
                # Aftertouch
                elif status == 0xD0 and len(data) >= 2:
                    print(f"👆 AFTERTOUCH - Porta: {port_idx} | "
                          f"Canal: {channel} | Pressure: {data[1]}")
            
            time.sleep(0.001)  # Pequeno delay para não sobrecarregar CPU
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 60)
        print("✅ Teste finalizado!")
        print("=" * 60)
        
        if last_cc:
            print("\n📋 RESUMO - Controles CC detectados:")
            print("-" * 60)
            seen_ccs = set()
            for key in sorted(last_cc.keys()):
                port, channel, cc = key.split('_')
                cc_tuple = (cc, channel, port)
                if cc_tuple not in seen_ccs:
                    seen_ccs.add(cc_tuple)
                    print(f"  CC#{cc:3s} - Canal {channel} - Porta {port}")
            
            print("\n💡 Para mapear no midi_map.yaml, adicione:")
            print("cc:")
            for key in sorted(last_cc.keys()):
                port, channel, cc = key.split('_')
                print(f"  {cc}: \"NomeDoInstrumento\"  # Controle detectado")
        else:
            print("\n⚠️  Nenhum controle CC foi detectado!")
            print("\n🔧 Possíveis soluções:")
            print("  1. Verifique se o XPS-30 está em modo MIDI CC (não modo interno)")
            print("  2. Acesse MENU > SYSTEM > CONTROLLER no XPS-30")
            print("  3. Configure os knobs S1/S2 para enviar CC")
            print("  4. Verifique se MIDI OUT está ativado no XPS-30")

if __name__ == "__main__":
    main()
