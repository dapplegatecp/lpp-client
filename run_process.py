import subprocess
import threading
import shlex

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

    def start(self):
        try:
            # Start the external program and capture its output
            self.process = subprocess.Popen(shlex.split(self.cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            # Create a thread to read and print the program's output
            def output_thread():
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    print(line.strip())

            output_thread = threading.Thread(target=output_thread)
            output_thread.start()

            # Wait for the program to complete and collect the return code
            return_code = self.process.wait()

            # Return the return code of the program
            return return_code
        except Exception as e:
            print(f"Error: {e}")
            return -1
        finally:
            self.process = None

def main():
    # Command to run an example program (replace with your own command)
    command = "ping 1.1.1.1"

    # Run the external program and get its return code
    program = RunProgram(command)

    # Create a control thread to handle user input (e.g., stopping the program)
    def control_thread(program):
        while True:
            user_input = input("Enter 'q' to quit: ")
            if user_input.lower() == 'q':
                program.interrupt() # Terminate the external program
                break

    control_thread = threading.Thread(target=control_thread, args=(program,))
    control_thread.start()

    return_code = program.start()

    # Wait for the control thread to finish
    control_thread.join()

    print(f"External program exited with return code: {return_code}")

if __name__ == "__main__":
    main()