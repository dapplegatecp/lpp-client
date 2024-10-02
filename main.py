import socket
import time
import threading
import subprocess
import shlex
import os

import logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger("lpp-client")

from csclient import CSClient
cs = CSClient("lpp-client", logger=logger)

class RunProgram:
    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None
        self.output_thread = None
    
    def quit(self):
        if self.process:
            self.process.kill()
            self.process = None

    def interrupt(self):
        if self.process:
            self.process.send_signal(subprocess.signal.SIGINT)

    def write(self, data):
        if self.process:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    def start(self):
        try:
            # Start the external program and capture its output
            self.process = subprocess.Popen(shlex.split(self.cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0)

            # Create a thread to read and print the program's output
            def output_thread():
                while True:
                    if not self.process:
                        break
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    logger.info(line.strip())

            output_thread = threading.Thread(target=output_thread)
            output_thread.daemon = True
            output_thread.start()

            # Wait for the program to complete and collect the return code
            return_code = self.process.wait()

            # Return the return code of the program
            return return_code
        except Exception as e:
            logger.error(f"Error: {e}")
            return -1
        finally:
            self.process = None

def handle_nmea(nmea, data=None, cs_path="/status/rtk/nmea"):
    if data is None:
        data = {}
    t = time.time()
    # prune data to last 30 seconds
    data = {k: v for k, v in data.items() if (t - k) < 30}
    data[t] = nmea
    cs_data = list(data.values())
    cs.put(cs_path, cs_data)
    return data

def un_thread_server(cs_path="/status/rtk/nmea"):
    """ Thread for reading from unix socket and logging the output"""
    socket_path = "/tmp/nmea.sock"
    data = {}
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as unix_socket:
        unix_socket.bind(socket_path)
        unix_socket.listen(1)
        while True:
            client_socket, addr = unix_socket.accept()
            with client_socket:
                buffer = ""
                while True:
                    chunk = client_socket.recv(8192).decode()
                    if not chunk:
                        break
                    buffer += chunk
                    while '\r\n' in buffer:
                        line, buffer = buffer.split('\r\n', 1)
                        if line:
                            logger.info(line)
                            data = handle_nmea(line, data=data, cs_path=cs_path)

def cs_get(path):
    return cs.get(path)

def get_appdata(key):
    appdata = cs_get("/config/system/sdk/appdata")
    return next((j['value'] for j in appdata if j['name'] == key), None)


def get_cellular_info(device=None):
    if device is None:
        device = get_appdata("lpp-client.device") or cs_get("/status/wan/primary_device")
    if not (device and device.startswith("mdm")):
        raise Exception("primary_device is not a modem")
    
    diag = cs_get(f"/status/wan/devices/{device}/diagnostics")
    plmn = diag['CUR_PLMN']
    mcc = plmn[:3]
    mnc = plmn[3:]
    tac = diag.get('TAC')
    imsi = diag['IMSI']
    cell_id = diag.get('CELL_ID').split(" ")[0]

    if not cell_id:
        cell_id =  diag['NR_CELL_ID']
        tac = plmn

    current_cellular = {"mcc": mcc, "mnc": mnc, "tac": tac, "cell_id": cell_id, "imsi": imsi}

    # cellular overrides
    current_cellular["mcc"] = get_appdata("lpp-client.mcc") or current_cellular["mcc"]
    current_cellular["mnc"] = get_appdata("lpp-client.mnc") or current_cellular["mnc"]
    current_cellular["tac"] = get_appdata("lpp-client.tac") or current_cellular["tac"]
    current_cellular["cell_id"] = get_appdata("lpp-client.cell_id") or current_cellular["cell_id"]
    current_cellular["imsi"] = get_appdata("lpp-client.imsi") or current_cellular["imsi"]

    return current_cellular

def get_cmd_params():
    host = get_appdata("lpp-client.host") or "129.192.82.125"
    port = get_appdata("lpp-client.port") or 5431
    serial = get_appdata("lpp-client.serial") or "/dev/ttyS1"
    baud = get_appdata("lpp-client.baud") or 115200
    output = get_appdata("lpp-client.output") or "un"
    format = get_appdata("lpp-client.format") or "osr"
    starting_cell_id = get_appdata("lpp-client.starting_cell_id") or None
    forwarding = get_appdata("lpp-client.forwarding") or ""
    flags = get_appdata("lpp-client.flags") or ""
    #flags are comma separated. For example:
    # "confidence-95to39,ura-override=2,ublox-clock-correction,force-continuity,sf055-default=3,sf042-default=1,increasing-siou"

    cs_path = get_appdata("lpp-client.path") or "/status/rtk/nmea"

    return {"host": host, "port": port, "serial": serial, "baud": baud, "output":output, "cs_path": cs_path, "format": format, "starting_cell_id": starting_cell_id, "forwarding": forwarding, "flags": flags}

if __name__ == "__main__":
    logger.info("Starting lpp client")

    params = get_cmd_params()
    cellular = get_cellular_info()
    logger.info(params)

    if params["cs_path"] == "/status/rtk/nmea": # the default
        if cs.get("/status/rtk") is None:
            cs.put("/status/rtk", {"nmea": []})

    if params["output"] == "un":
        un_thread = threading.Thread(target=un_thread_server, args=(params["cs_path"],))
        un_thread.daemon = True
        un_thread.start()
        output_param = "--nmea-export-un=/tmp/nmea.sock"
    else:
        ip, port = params['output'].split(':')
        output_param = f"--nmea-export-tcp={ip} --nmea-export-tcp-port={port}"

    format = "osr"
    additional_flags = []
    if params["format"] == "osr":
        format = "osr"
        if params["forwarding"]:
            additional_flags =["format=lrf-uper"]
    else:
        format = "ssr"
        if params["forwarding"]:
            additional_flags =["format=lrf-uper"]
        else:
            additional_flags =["format=spartn"]

    additional_flags += [f.strip() for f in params["flags"].split(",")]
    additional_flags = "--".join(additional_flags)

    cmd = f"/app/example-lpp {format} --prm {additional_flags} -h {params['host']} --port {params['port']} -c {cellular['mcc']} -n {cellular['mnc']} -t {cellular['tac']} -i {params['starting_cell_id'] or cellular['cell_id']} --imsi {cellular['imsi']} --nmea-serial {params['serial']} --nmea-serial-baud {params['baud']} --ctrl-stdin {output_param}"
    logger.info(cmd)
    program = RunProgram(cmd)

    # Create a control thread to handle user input (e.g., stopping the program)
    def control_thread(program, current_params, current_cellular):
        logger.info("Periodically checking for changes")
        while True:
            time.sleep(10)
            if program.process is None:
                logger.info("Program terminated")
                break
            new_params = get_cmd_params()
            if new_params != current_params:
                current_params = new_params
                logger.info("params changed", current_params)
                program.interrupt() # Terminate the external program
                break
            new_cellular = get_cellular_info()
            if new_cellular != current_cellular:
                current_cellular = new_cellular
                logger.info("cellular info changed", current_cellular)
                cmd = f"/CID,L,{current_cellular['mnc']},{current_cellular['mcc']},{current_cellular['tac']},{current_cellular['cell_id']}\r\n"
                program.write(cmd)

    ct = threading.Thread(target=control_thread, args=(program,params,cellular))
    ct.daemon = True
    ct.start()

    program.start()

    ct.join()

    logger.info("Exiting program, hopefully restarting...")