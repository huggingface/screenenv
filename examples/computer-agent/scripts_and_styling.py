SANDBOX_HTML_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Oxanium:wght@200..800&display=swap');
</style>
    <h1 style="color:var(--color-accent);margin:0;">Open Computer Agent - <i>Powered by <a href="https://github.com/huggingface/smolagents">smolagents</a></i><h1>
<div class="sandbox-container" style="margin:0;">
    <div class="status-bar">
        <div class="status-indicator {status_class}"></div>
        <div class="status-text">{status_text}</div>
    </div>
    <iframe id="sandbox-iframe"
        src="{stream_url}" 
        class="sandbox-iframe"
        style="display: block;"
        allowfullscreen>
    </iframe>
    <img src="https://huggingface.co/datasets/mfarre/servedfiles/resolve/main/blue_screen_of_death.gif" class="bsod-image" style="display: none;"/>
    <img src="https://huggingface.co/datasets/m-ric/images/resolve/main/HUD_thom.png" class="sandbox-frame" />
</div>
"""

SANDBOX_CSS_TEMPLATE = """
.modal-container {
    margin: var(--size-16) auto!important;
}

.sandbox-container {
    position: relative;
    width: 910px;
    overflow: hidden;
    margin: auto;
}
.sandbox-container {
    height: 800px;
}
.sandbox-frame {
    display: none;
    position: absolute;
    top: 0;
    left: 0;
    width: 910px;
    height: 800px;
    pointer-events:none;
}

.sandbox-iframe, .bsod-image {
    position: absolute;
    width: <<WIDTH>>px;
    height: <<HEIGHT>>px;
    border: 4px solid #444444;
    transform-origin: 0 0;
}

/* Colored label for task textbox */
.primary-color-label label span {
    font-weight: bold;
    color: var(--color-accent);
}

/* Status indicator light */
.status-bar {
    display: flex;
    flex-direction: row;
    align-items: center;
    flex-align:center;
    z-index: 100;
}

.status-indicator {
    width: 15px;
    height: 15px;
    border-radius: 50%;
}

.status-text {
    font-size: 16px;
    font-weight: bold;
    padding-left: 8px;
    text-shadow: none;
}

.status-interactive {
    background-color: #2ecc71;
    animation: blink 2s infinite;  
}

.status-view-only {
    background-color: #e74c3c;
}

.status-error {
    background-color: #e74c3c;
    animation: blink-error 1s infinite;
}

@keyframes blink-error {
    0% { background-color: rgba(231, 76, 60, 1); }
    50% { background-color: rgba(231, 76, 60, 0.4); }
    100% { background-color: rgba(231, 76, 60, 1); }
}

@keyframes blink {
    0% { background-color: rgba(46, 204, 113, 1); }  /* Green at full opacity */
    50% { background-color: rgba(46, 204, 113, 0.4); }  /* Green at 40% opacity */
    100% { background-color: rgba(46, 204, 113, 1); }  /* Green at full opacity */
}

#chatbot {
    height:1000px!important;
}
#chatbot .role {
    max-width:95%
}

#chatbot .bubble-wrap {
    overflow-y: visible;
}

.logo-container {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
    box-sizing: border-box;
    gap: 5px;

.logo-item {
    display: flex;
    align-items: center;
    padding: 0 30px;
    gap: 10px;
    text-decoration: none!important;
    color: #f59e0b;
    font-size:17px;
}
.logo-item:hover {
    color: #935f06!important;
}
"""

FOOTER_HTML = """
<h3 style="text-align: center; margin-top:50px;"><i>Powered by open source:</i></h2>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
<div class="logo-container">
    <a class="logo-item" href="https://github.com/huggingface/smolagents"><i class="fa fa-github"></i>smolagents</a>
    <a class="logo-item" href="https://huggingface.co/Qwen/Qwen2-VL-72B-Instruct"><i class="fa fa-github"></i>Qwen2-VL-72B</a>
    <a class="logo-item" href="https://github.com/e2b-dev/desktop"><i class="fa fa-github"></i>E2B Desktop</a>
</div>
"""

CUSTOM_JS = """function() {
    document.body.classList.add('dark');

    // Function to check if sandbox is timing out
    const checkSandboxTimeout = function() {
        const timeElement = document.getElementById('sandbox-creation-time');
        
        if (timeElement) {
            const creationTime = parseFloat(timeElement.getAttribute('data-time'));
            const timeoutValue = parseFloat(timeElement.getAttribute('data-timeout'));
            const currentTime = Math.floor(Date.now() / 1000); // Current time in seconds
            
            const elapsedTime = currentTime - creationTime;
            console.log("Sandbox running for: " + elapsedTime + " seconds of " + timeoutValue + " seconds");
            
            // If we've exceeded the timeout, show BSOD
            if (elapsedTime >= timeoutValue) {
                console.log("Sandbox timeout! Showing BSOD");
                showBSOD('Error');
                // Don't set another timeout, we're done checking
                return;
            }
        }
        
        // Continue checking every 5 seconds
        setTimeout(checkSandboxTimeout, 5000);
    };
    
    const showBSOD = function(statusText = 'Error') {
        console.log("Showing BSOD with status: " + statusText);
        const iframe = document.getElementById('sandbox-iframe');
        const bsod = document.getElementById('bsod-image');
        
        if (iframe && bsod) {
            iframe.style.display = 'none';
            bsod.style.display = 'block';

            // Update status indicator
            const statusIndicator = document.querySelector('.status-indicator');
            const statusTextElem = document.querySelector('.status-text');

            if (statusIndicator) {
                statusIndicator.className = 'status-indicator status-error';
            }
            
            if (statusTextElem) {
                statusTextElem.innerText = statusText;
            }
        }
    };

    const resetBSOD = function() {
        console.log("Resetting BSOD display");
        const iframe = document.getElementById('sandbox-iframe');
        const bsod = document.getElementById('bsod-image');
        
        if (iframe && bsod) {
            if (bsod.style.display === 'block') {
                // BSOD is currently showing, reset it
                iframe.style.display = 'block';
                bsod.style.display = 'none';
                console.log("BSOD reset complete");
                return true; // Indicates reset was performed
            }
        }
        return false; // No reset needed
    };
    
    // Function to monitor for error messages
    const monitorForErrors = function() {
        console.log("Error monitor started");
        const resultsInterval = setInterval(function() {
            const resultsElements = document.querySelectorAll('textarea, .output-text');
            for (let elem of resultsElements) {
                const content = elem.value || elem.innerText || '';
                if (content.includes('Error running agent')) {
                    console.log("Error detected!");
                    showBSOD('Error');
                    clearInterval(resultsInterval);
                    break;
                }
            }
        }, 1000);
    };
    
    
    // Start monitoring for timeouts immediately
    checkSandboxTimeout();
    
    // Start monitoring for errors
    setTimeout(monitorForErrors, 3000);
    
    // Also monitor for errors after button clicks
    document.addEventListener('click', function(e) {
        if (e.target.tagName === 'BUTTON') {
            if (e.target.innerText === "Let's go!") {
                resetBSOD();
            }
            setTimeout(monitorForErrors, 3000);
        }
    });

    // Set up an interval to click the refresh button every 5 seconds
    setInterval(function() {
        const btn = document.getElementById('refresh-log-btn');
        if (btn) btn.click();
    }, 5000);

    // Force dark mode
    const params = new URLSearchParams(window.location.search);
    if (!params.has('__theme')) {
        params.set('__theme', 'dark');
        window.location.search = params.toString();
    }
}
"""


def apply_theme(minimalist_mode: bool):
    if not minimalist_mode:
        return """
            <style>
            .sandbox-frame {
                display: block!important;
            }

            .sandbox-iframe, .bsod-image {
                /* top: 73px; */
                top: 99px;
                /* left: 74px; */
                left: 110px;
            }
            .sandbox-iframe {
                transform: scale(0.535);
            }

            .status-bar {
                position: absolute;
                bottom: 88px;
                left: 355px;
            }
            .status-text {
                color: #fed244;
            }
            </style>
        """
    else:
        return """
            <style>
            .sandbox-container {
                height: 700px!important;
            }
            .sandbox-iframe {
                transform: scale(0.7);
            }
            </style>
        """
