from http.server import BaseHTTPRequestHandler
import sys
import traceback
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Try to import the FastAPI app
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            
            info = {
                "python_version": sys.version,
                "cwd": os.getcwd(),
                "dir_contents": os.listdir(os.path.dirname(__file__)),
                "sys_path": sys.path[:5],
            }
            
            # Try imports one at a time
            steps = []
            try:
                from models import risk_engine
                steps.append("risk_engine OK")
            except Exception as e:
                steps.append(f"risk_engine FAIL: {e}")
            
            try:
                from models import environmental
                steps.append("environmental OK")
            except Exception as e:
                steps.append(f"environmental FAIL: {e}")
                
            try:
                from services import facility_mfl
                steps.append("facility_mfl OK")
            except Exception as e:
                steps.append(f"facility_mfl FAIL: {e}")
            
            try:
                from routers import strategic
                steps.append("strategic OK")
            except Exception as e:
                steps.append(f"strategic FAIL: {e}")
            
            info["import_steps"] = steps
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            import json
            self.wfile.write(json.dumps(info, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(traceback.format_exc().encode())
