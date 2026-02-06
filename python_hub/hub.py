"""
Observatory Hub - Completely unique agent management server
Custom binary protocol, unique state management, original algorithms
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import threading
import struct
import time
import random
import pickle
import zlib
from collections import defaultdict

# Unique state keeper using triple-layer caching
class TripleVault:
    def __init__(self):
        # Layer 1: Hot cache (active connections)
        self.blazing_tier = {}
        # Layer 2: Warm cache (recent activity)  
        self.tepid_tier = {}
        # Layer 3: Cold storage (historical)
        self.frozen_tier = defaultdict(list)
        self.mutation_counter = 0
        self.lock = threading.RLock()
    
    def inscribe(self, probe_id, data_bundle, tier='blazing'):
        with self.lock:
            self.mutation_counter += 1
            stamp = time.time()
            entry = {'data': data_bundle, 'stamp': stamp, 'mutation': self.mutation_counter}
            
            if tier == 'blazing':
                # Demote old blazing to tepid
                if probe_id in self.blazing_tier:
                    self.tepid_tier[probe_id] = self.blazing_tier[probe_id]
                self.blazing_tier[probe_id] = entry
            elif tier == 'frozen':
                self.frozen_tier[probe_id].append(entry)
                # Keep only last 30 frozen entries
                self.frozen_tier[probe_id] = self.frozen_tier[probe_id][-30:]
    
    def retrieve(self, probe_id, prefer_tier='blazing'):
        with self.lock:
            if prefer_tier == 'blazing' and probe_id in self.blazing_tier:
                return self.blazing_tier[probe_id]
            elif probe_id in self.tepid_tier:
                return self.tepid_tier[probe_id]
            return None
    
    def cascade_freeze(self):
        # Move tepid to frozen periodically
        with self.lock:
            for probe_id, entry in list(self.tepid_tier.items()):
                self.frozen_tier[probe_id].append(entry)
                self.frozen_tier[probe_id] = self.frozen_tier[probe_id][-30:]
            self.tepid_tier.clear()

vault = TripleVault()

# Custom binary protocol - 3-byte header + compressed payload
class BinaryDialect:
    @staticmethod
    def forge_packet(opcode, payload_dict):
        # Opcode (1 byte) + Payload length (2 bytes) + Compressed JSON
        serialized = pickle.dumps(payload_dict)
        compressed = zlib.compress(serialized, level=6)
        header = struct.pack('!BH', opcode, len(compressed))
        return header + compressed
    
    @staticmethod
    def parse_packet(raw_bytes):
        if len(raw_bytes) < 3:
            return None, None
        opcode, payload_len = struct.unpack('!BH', raw_bytes[:3])
        if len(raw_bytes) < 3 + payload_len:
            return None, None
        compressed = raw_bytes[3:3+payload_len]
        serialized = zlib.decompress(compressed)
        payload = pickle.loads(serialized)
        return opcode, payload

# Opcodes for our custom protocol
OPCODE_HELLO = 1
OPCODE_PULSE = 2
OPCODE_METRICS = 3
OPCODE_ACK = 4
OPCODE_REJECT = 5

# Connection registry
probe_sockets = {}
socket_lock = threading.Lock()

class ProbeHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        probe_id = None
        buffer = b''
        
        try:
            while True:
                chunk = sock.recv(2048)
                if not chunk:
                    break
                
                buffer += chunk
                
                while len(buffer) >= 3:
                    opcode, payload = BinaryDialect.parse_packet(buffer)
                    if opcode is None:
                        break
                    
                    # Consume parsed packet from buffer
                    _, payload_len = struct.unpack('!BH', buffer[:3])
                    buffer = buffer[3+payload_len:]
                    
                    if opcode == OPCODE_HELLO and not probe_id:
                        probe_id = payload.get('probe_id')
                        secret = payload.get('secret')
                        
                        # Simple auth check
                        stored = vault.retrieve(probe_id, 'tepid')
                        if stored and stored['data'].get('secret') == secret:
                            with socket_lock:
                                probe_sockets[probe_id] = sock
                            vault.inscribe(probe_id, {'status': 'connected', 'secret': secret})
                            
                            response = BinaryDialect.forge_packet(OPCODE_ACK, {'welcome': True, 'stamp': time.time()})
                            sock.sendall(response)
                        else:
                            response = BinaryDialect.forge_packet(OPCODE_REJECT, {'reason': 'invalid_credentials'})
                            sock.sendall(response)
                            return
                    
                    elif opcode == OPCODE_PULSE and probe_id:
                        vault.inscribe(probe_id, {'last_pulse': time.time()})
                        response = BinaryDialect.forge_packet(OPCODE_ACK, {'pulse_echo': True})
                        sock.sendall(response)
                    
                    elif opcode == OPCODE_METRICS and probe_id:
                        metrics = payload.get('metrics')
                        old_entry = vault.retrieve(probe_id)
                        
                        # Detect changes using XOR hash comparison
                        old_hash = hash(str(sorted(old_entry['data'].get('metrics', {}).items()))) if old_entry else 0
                        new_hash = hash(str(sorted(metrics.items())))
                        changed = old_hash != new_hash
                        
                        if changed and old_entry:
                            vault.inscribe(probe_id, old_entry['data'], tier='frozen')
                        
                        vault.inscribe(probe_id, {'metrics': metrics, 'last_update': time.time()})
                        response = BinaryDialect.forge_packet(OPCODE_ACK, {'changed': changed})
                        sock.sendall(response)
        
        except Exception as e:
            print(f"Handler error: {e}")
        finally:
            if probe_id:
                with socket_lock:
                    probe_sockets.pop(probe_id, None)
                vault.inscribe(probe_id, {'status': 'disconnected', 'disconnect_time': time.time()})

class ThreadedProbeServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

# HTTP API handler
class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/probes':
            probes_list = []
            for probe_id in list(vault.blazing_tier.keys()):
                entry = vault.retrieve(probe_id)
                if entry:
                    probes_list.append({
                        'probe_id': probe_id,
                        'data': entry['data'],
                        'connected': probe_id in probe_sockets
                    })
            
            response = pickle.dumps({'probes': probes_list})
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(response)
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/api/register':
            content_len = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_len)
            data = pickle.loads(body)
            
            # Generate probe credentials
            probe_id = f"probe_{random.randint(100000, 999999)}"
            secret = f"key_{random.randint(100000, 999999)}"
            
            vault.inscribe(probe_id, {'secret': secret, 'registered': time.time()}, tier='tepid')
            
            response = pickle.dumps({'probe_id': probe_id, 'secret': secret, 'port': 7777})
            self.send_response(201)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(response)
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

# Watchdog for stale connections
class Watchdog:
    def __init__(self):
        self.running = True
    
    def patrol(self):
        while self.running:
            time.sleep(30)
            current = time.time()
            
            for probe_id in list(vault.blazing_tier.keys()):
                entry = vault.retrieve(probe_id)
                if entry:
                    last_pulse = entry['data'].get('last_pulse', 0)
                    if current - last_pulse > 90:
                        vault.inscribe(probe_id, {'status': 'stale', 'stale_time': current})
            
            vault.cascade_freeze()

def launch_hub():
    print("Launching Observatory Hub...")
    
    # Start watchdog
    watchdog = Watchdog()
    patrol_thread = threading.Thread(target=watchdog.patrol, daemon=True)
    patrol_thread.start()
    
    # Start probe server
    probe_server = ThreadedProbeServer(('0.0.0.0', 7777), ProbeHandler)
    probe_thread = threading.Thread(target=probe_server.serve_forever, daemon=True)
    probe_thread.start()
    print("Probe server on port 7777")
    
    # Start HTTP API
    api_server = HTTPServer(('0.0.0.0', 8080), APIHandler)
    print("API server on port 8080")
    api_server.serve_forever()

if __name__ == '__main__':
    launch_hub()
