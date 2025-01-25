<!DOCTYPE html>
<html>
<head>
    <title>LPP Client Configuration</title>
    <style>
        :root {
            --primary-color: #2c3e50;
            --accent-color: #3498db;
            --bg-color: #f5f6fa;
            --text-color: #2c3e50;
            --border-radius: 4px;
            --input-height: 36px;
        }

        body {
            font-family: Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }

        h1, h2 {
            color: var(--primary-color);
            margin-bottom: 1.5rem;
        }

        form {
            background-color: #fff;
            padding: 15px;
            border-radius: var(--border-radius);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            max-width: 800px;
            margin-bottom: 30px;
        }

        .form-field {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 5px 0;
            border: 1px solid transparent;
            border-radius: var(--border-radius);
            transition: border-color 0.3s, box-shadow 0.3s;
        }

        .form-field:focus-within {
            border-color: var(--accent-color);
            box-shadow: 0 0 2px rgba(52, 152, 219, 0.5);
        }

        label {
            min-width: 150px;
            text-align: left;
            padding: 0 10px;
            font-weight: bold;
            margin-bottom: 2px;
            font-size: 14px;
        }

        input[type="text"] {
            flex: 1;
            padding: 5px 10px;
            margin-right: 5px;
            border: 1px solid #ccc;
            border-radius: var(--border-radius);
            font-size: 14px;
            box-sizing: border-box;
        }

        input[type="text"]:focus {
            border-color: var(--accent-color);
            outline: none;
            box-shadow: 0 0 5px rgba(52, 152, 219, 0.5);
        }

        input[type="submit"] {
            padding: 8px 16px;
            background-color: var(--accent-color);
            color: #fff;
            border: none;
            border-radius: var(--border-radius);
            font-size: 13px;
            cursor: pointer;
            transition: background-color 0.3s;
        }

        input[type="submit"]:hover {
            background-color: #2980b9;
        }

        .connection-status {
            padding: 10px 15px;
            margin-bottom: 15px;
            border-radius: var(--border-radius);
            font-weight: bold;
        }

        .connected { background-color: #d4edda; color: #155724; }
        .disconnected { background-color: #f8d7da; color: #721c24; }
        .connecting { background-color: #fff3cd; color: #856404; }

        #logs {
            font-family: "Courier New", Courier, monospace;
            white-space: pre-wrap;
            border: 1px solid #ccc;
            border-radius: var(--border-radius);
            padding: 15px;
            height: 900px;
            overflow-y: scroll;
            background-color: #ffffff;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
            resize: vertical;
            min-height: 300px;
            max-height: 1200px;
        }

        .log-error { color: red; }
        .log-warning { color: #ffae42; }
        .log-debug { color: #999; }

        @media (max-width: 600px) {
            .form-field {
                flex-direction: column;
                align-items: flex-start;
            }

            label {
                margin-bottom: 5px;
                padding-left: 0;
            }

            input[type="text"] {
                margin-right: 0;
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <h2>LPP Client Configuration</h2>
    <form action="/update" method="post">
        % for key, value in config.items():
            <div class="form-field">
                <label for="{{key}}">{{key.replace('_', ' ').title()}}:</label>
                <input type="text" id="{{key}}" name="{{key}}" value="{{value}}">
            </div>
        % end
        <input type="submit" value="Update Configuration">
    </form>

    <h2>Logs</h2>
    <div class="connection-status"></div>
    <div id="logs"></div>

    <script>
        const logDiv = document.getElementById('logs');
        const statusDiv = document.querySelector('.connection-status');
        let eventSource = null;
        let reconnectAttempt = 0;
        const maxReconnectAttempts = 5;
        
        function connectSSE() {
            if (eventSource) {
                eventSource.close();
            }

            function handleNewLogLine(line) {
                let className = '';
                if (line.includes('ERROR')) className = 'log-error';
                else if (line.includes('WARNING')) className = 'log-warning';
                else if (line.includes('DEBUG')) className = 'log-debug';

                const newLine = document.createElement('div');
                newLine.className = className;
                newLine.textContent = line;
                logDiv.appendChild(newLine);
                logDiv.scrollTop = logDiv.scrollHeight;
            }

            statusDiv.textContent = 'Connecting...';
            statusDiv.className = 'connection-status connecting';
            
            eventSource = new EventSource('/logs');
            
            eventSource.onopen = () => {
                statusDiv.textContent = 'Connected';
                statusDiv.className = 'connection-status connected';
                reconnectAttempt = 0;
            };

            eventSource.onmessage = (event) => {
                const line = event.data;
                handleNewLogLine(line);
            };

            eventSource.onerror = (error) => {
                eventSource.close();
                statusDiv.textContent = 'Disconnected';
                statusDiv.className = 'connection-status disconnected';
                
                if (reconnectAttempt < maxReconnectAttempts) {
                    reconnectAttempt++;
                    setTimeout(connectSSE, 1000 * reconnectAttempt);
                } else {
                    statusDiv.textContent = 'Connection failed after multiple attempts';
                }
            };
        }

        // Start connection
        connectSSE();

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            if (eventSource) {
                eventSource.close();
            }
        });
    </script>
    
</body>
</html>