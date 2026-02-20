"""
Flask backend for Anthropic Claude Features Demo.
Converted from claude.ipynb notebook.
"""

import os
import json
import time
import uuid
import copy
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from anthropic import AnthropicFoundry
from anthropic.types.beta import BetaTextBlock, BetaToolUseBlock
from team_expense_api import get_custom_budget, get_expenses, get_team_members

app = Flask(__name__, static_folder=None)
CORS(app)

# --- Dynamic Configuration (set via /api/configure) ---
_config = {
    "base_url": None,
    "api_key": None,
    "deployment_name": None,
    "configured": False,
}

# Well-known Anthropic model/deployment names for the dropdown
AVAILABLE_MODELS = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-opus-4-6",
    "claude-haiku-4-5",
    "claude-opus-4-1"
]


@app.route("/api/configure", methods=["POST"])
def configure():
    """Set the Claude endpoint, API key and model deployment name."""
    body = request.json or {}
    endpoint = body.get("endpoint", "").strip().rstrip("/")
    api_key = body.get("apiKey", "").strip()
    model = body.get("model", "").strip()

    if not endpoint or not api_key or not model:
        return jsonify({"error": "endpoint, apiKey, and model are all required."}), 400

    # Quick validation – try to create a client and list models
    try:
        test_client = AnthropicFoundry(base_url=endpoint, api_key=api_key)
        # Lightweight check: just create the client; we can't easily ping without a call
        _config["base_url"] = endpoint
        _config["api_key"] = api_key
        _config["deployment_name"] = model
        _config["configured"] = True
        return jsonify({"ok": True, "model": model})
    except Exception as e:
        return jsonify({"error": f"Configuration failed: {str(e)}"}), 400


@app.route("/api/config-status", methods=["GET"])
def config_status():
    """Return whether the backend has been configured."""
    return jsonify({
        "configured": _config["configured"],
        "model": _config["deployment_name"],
        "endpoint": _config["base_url"],
    })


@app.route("/api/models", methods=["GET"])
def list_models():
    """Return available model deployment names."""
    return jsonify(AVAILABLE_MODELS)


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Load Microsoft 2025 Annual Report for Prompt Caching demo ---
_ANNUAL_REPORT_PATH = os.path.join(os.path.dirname(__file__), "uploads", "Microsoft 2025 Annual Report.html")
_ANNUAL_REPORT_CONTENT = ""
if os.path.exists(_ANNUAL_REPORT_PATH):
    with open(_ANNUAL_REPORT_PATH, "r", encoding="utf-8") as _f:
        _ANNUAL_REPORT_CONTENT = _f.read()
    print(f"Loaded Annual Report: {len(_ANNUAL_REPORT_CONTENT)} characters")
else:
    print(f"WARNING: Annual Report not found at {_ANNUAL_REPORT_PATH}")

_CACHE_TIMESTAMP = int(time.time())

# Store the first-run baseline time and timestamp for prompt caching
_baseline_time = None      # float — first-run response time
_baseline_timestamp = None  # epoch — when baseline was recorded


def get_client():
    """Create and return an AnthropicFoundry client."""
    if not _config["configured"]:
        raise RuntimeError("Backend not configured. Call /api/configure first.")
    return AnthropicFoundry(base_url=_config["base_url"], api_key=_config["api_key"])


def get_model():
    """Return the currently configured deployment/model name."""
    return _config["deployment_name"]


# ============================================================
# Feature definitions – shown in the React dropdown
# ============================================================
FEATURES = [
    {
        "id": "web_search",
        "name": "🔍 Web Search",
        "description": "Ask Claude a question and it will search the web for up-to-date information before answering.",
        "category": "Tools",
        "availableOn": "Available on Microsoft Foundry and Google Vertex only",
        "hasInput": True,
        "inputLabel": "Ask a question",
        "inputPlaceholder": "What is Microsoft Foundry?",
    },
    {
        "id": "web_fetch",
        "name": "🌐 Web Fetch",
        "description": "Retrieve full content from web pages and PDF documents for in-depth analysis without custom scraping infrastructure​.",
        "category": "Tools",
        "exclusive": True,
        "hasInput": True,
        "inputLabel": "Enter a URL to analyze",
        "inputPlaceholder": "Please analyze the content at https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-foundry?view=foundry&preserve-view=true",
    },
    {
        "id": "files_api",
        "name": "📎 Files API",
        "description": "Upload files once and reference across unlimited API calls. Reduces bandwidth costs by up to 90% for document-heavy applications.",
        "category": "Core",
        "exclusive": True,
        "hasInput": True,
        "hasFileUpload": True,
        "inputLabel": "Ask a question about the uploaded file",
        "inputPlaceholder": "Please summarize this document for me.",
    },
    {
        "id": "code_execution",
        "name": "💻 Code Execution and Programmatic Tool Calling",
        "description": "Run Python in sandboxed environments for data analysis without external infrastructure. With PTC, Claude calls tools directly from code containers, reducing token use by 40% and latency by 60%.​",
        "category": "Tools",
        "exclusive": True,
        "scenario": "In this scenario, we need to analyze team expenses and identify which employees have exceeded their budgets. Traditionally, we might manually pull expense reports for each person, sum up their expenses by category, compare against budget limits (checking for custom budget exceptions), and compile a report. Instead, we will ask Claude to perform this analysis for us, using the available tools to retrieve team data, fetch potentially hundreds of expense line items with rich metadata, and determine who has gone over budget.",
        "hasInput": True,
        "inputReadOnly": True,
        "inputLabel": "Ask a question about team expenses.Click on the scenario button to understand more on the context.",
        "inputPlaceholder": "Which engineering team members exceeded their Q3 travel budget? Standard quarterly travel budget is $5,000. However, some employees have custom budget limits. For anyone who exceeded the $5,000 standard budget, check if they have a custom budget exception.",
    },
    {
        "id": "prompt_caching",
        "name": "⚡ Prompt Caching",
        "description": "See how 1-hour prompt caching reduces latency and cost on repeated queries.Extended cache duration supports intermittent workloads (6-60 minute intervals)",
        "category": "Core",
        "exclusive": True,
        "hasInput": True,
        "inputReadOnly": True,
        "inputLabel": "Question",
        "inputPlaceholder": "Revenue in 2025? Only return the value using Microsoft Annual report 2025",
    },
    {
        "id": "skills",
        "name": "🛠️ Document Generation",
        "description": "Build agents that create PowerPoint presentations, Excel spreadsheets, Word documents, and PDFs programmatically through API calls.It helps eliminate manual document creation workflows and enables documentautomation at enterprise scale.",
        "category": "Agent Skills",
        "exclusive": True,
        "hasInput": True,
        "inputLabel": "Describe the document you want",
        "inputPlaceholder": "Write a 2-page report on the benefits of agentic AI architecture",
        "subFeatures": [
            {
                "id": "generate_docx",
                "name": "📄 Word Document",
                "description": "Generate a .docx file",
                "inputPlaceholder": "Write a 2-page report on the benefits of agentic AI architecture ",
            },
            {
                "id": "generate_pdf",
                "name": "📕 PDF Document",
                "description": "Generate a .pdf file",
                "inputPlaceholder": "Generate a PDF invoice template",
            },
        ],
    },
]


@app.route("/api/debug-static", methods=["GET"])
def debug_static():
    """Debug: check where static files are."""
    info = {
        "__file__": __file__,
        "abspath": os.path.abspath(__file__),
        "dirname": os.path.dirname(os.path.abspath(__file__)),
        "cwd": os.getcwd(),
        "REACT_BUILD": REACT_BUILD,
        "REACT_BUILD_exists": os.path.exists(REACT_BUILD),
    }
    if os.path.exists(REACT_BUILD):
        info["REACT_BUILD_contents"] = os.listdir(REACT_BUILD)
        static_sub = os.path.join(REACT_BUILD, "static")
        if os.path.exists(static_sub):
            info["static_sub_contents"] = os.listdir(static_sub)
            js_sub = os.path.join(static_sub, "js")
            if os.path.exists(js_sub):
                info["static_js_contents"] = os.listdir(js_sub)
            css_sub = os.path.join(static_sub, "css")
            if os.path.exists(css_sub):
                info["static_css_contents"] = os.listdir(css_sub)
    return jsonify(info)


@app.route("/api/features", methods=["GET"])
def get_features():
    """Return the list of available features."""
    return jsonify(FEATURES)


# ------------------------------------------------------------------
# Streaming helper – yields Server-Sent Events (SSE)
# ------------------------------------------------------------------
def sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ------------------------------------------------------------------
# Feature runners
# ------------------------------------------------------------------

def _run_skill(skill_id: str, user_input: str, file_ext: str):
    """Generic runner for skills that produce a file (docx, pptx, pdf)."""
    client = get_client()

    yield sse_event("status", {"message": f"⏳ Claude is generating your {file_ext.upper()} file..."})

    response = client.beta.messages.create(
        model=get_model(),
        max_tokens=16384,
        betas=["code-execution-2025-08-25", "skills-2025-10-02"],
        container={
            "skills": [
                {"type": "anthropic", "skill_id": skill_id, "version": "latest"}
            ]
        },
        messages=[{"role": "user", "content": user_input}],
        tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
    )

    # Stream back the text blocks so the user sees progress
    for block in response.content:
        if hasattr(block, "text"):
            yield sse_event("token", {"text": block.text + "\n"})

    # Extract file_id
    yield sse_event("status", {"message": "📥 Extracting generated file..."})

    file_id = None
    for block in response.content:
        if block.type == "bash_code_execution_tool_result":
            result = block.content
            if hasattr(result, "content") and result.content:
                for output in result.content:
                    if (
                        output.type == "bash_code_execution_output"
                        and hasattr(output, "file_id")
                    ):
                        file_id = output.file_id
                        break

    if file_id:
        file_content = client.beta.files.download(
            file_id=file_id, betas=["files-api-2025-04-14"]
        )
        filename = f"{uuid.uuid4().hex[:8]}.{file_ext}"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            file_content.write_to_file(f.name)

        yield sse_event("file", {"filename": filename, "fileType": file_ext})
        yield sse_event("done", {"message": f"✅ {file_ext.upper()} file generated successfully!"})
    else:
        yield sse_event("error", {"message": "Could not extract file from response."})
        yield sse_event("done", {"message": "⚠️ No file was produced."})


# ------------------------------------------------------------------
# File upload storage
# ------------------------------------------------------------------
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Store uploaded file_ids per session (simple in-memory map)
_uploaded_files = {}   # upload_key -> anthropic file_id


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Upload a file to Anthropic Files API and return a reference key."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    # Determine MIME type
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".json": "application/json",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    ext = os.path.splitext(f.filename)[1].lower()
    mime_type = mime_map.get(ext, "application/octet-stream")

    # Save locally first
    local_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{f.filename}")
    f.save(local_path)

    try:
        client = get_client()
        result = client.beta.files.upload(
            file=(f.filename, open(local_path, "rb"), mime_type),
            betas=["files-api-2025-04-14"],
        )
        print(result)
        file_id = result.id
        print(file_id)
        upload_key = uuid.uuid4().hex[:12]
        _uploaded_files[upload_key] = {"file_id": file_id, "filename": f.filename}
        return jsonify({"uploadKey": upload_key, "filename": f.filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_files_api(user_input: str, upload_key: str = None):
    """Ask Claude questions about an uploaded file."""
    if not upload_key or upload_key not in _uploaded_files:
        yield sse_event("error", {"message": "Please upload a file first."})
        yield sse_event("done", {"message": "❌ No file uploaded."})
        return

    upload_info = _uploaded_files[upload_key]
    file_id = upload_info["file_id"]
    filename = upload_info["filename"]

    client = get_client()
    yield sse_event("status", {"message": f"📎 Analyzing {filename}..."})

    response = client.beta.messages.create(
        model=get_model(),
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_input},
                    {
                        "type": "document",
                        "source": {
                            "type": "file",
                            "file_id": file_id,
                        },
                    },
                ],
            }
        ],
        betas=["files-api-2025-04-14"],
    )

    for block in response.content:
        if hasattr(block, "text"):
            yield sse_event("token", {"text": block.text})

    yield sse_event("done", {"message": f"✅ Analysis of {filename} complete!"})


def run_code_execution(user_input: str, upload_key: str = None):
    """Advanced tool use: PTC agent with team expense tools.
    Uses code_execution + allowed_callers so Claude can call tools from code.
    Streams progress, tool calls, and final result via SSE.
    """
    client = get_client()

    # --- Team expense tool definitions (with allowed_callers for PTC) ---
    tool_definitions = [
        {
            "name": "get_team_members",
            "description": 'Returns a list of team members for a given department. Each team member includes their ID, name, role, level (junior, mid, senior, staff, principal), and contact information. Available departments are: engineering, sales, and marketing.\n\nRETURN FORMAT: Returns a JSON string containing an ARRAY of team member objects. Parse with json.loads() to get a list.',
            "input_schema": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "The department name. Case-insensitive.",
                    }
                },
                "required": ["department"],
            },
        },
        {
            "name": "get_expenses",
            "description": "Returns all expense line items for a given employee in a specific quarter. Each expense includes date, category, description, amount (in USD), status (approved, pending, rejected), merchant name, payment method, and project codes. IMPORTANT: Only expenses with status='approved' should be counted toward budget limits.\n\nRETURN FORMAT: Returns a JSON string containing an ARRAY of expense objects.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "The unique employee identifier",
                    },
                    "quarter": {
                        "type": "string",
                        "description": "Quarter identifier: 'Q1', 'Q2', 'Q3', or 'Q4'",
                    },
                },
                "required": ["employee_id", "quarter"],
            },
        },
        {
            "name": "get_custom_budget",
            "description": 'Get the custom quarterly travel budget for a specific employee. Most employees have a standard $5,000 quarterly travel budget. However, some employees have custom budget exceptions.\n\nRETURN FORMAT: Returns a JSON string containing a SINGLE OBJECT with has_custom_budget, travel_budget, reason fields.',
            "input_schema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The unique employee identifier",
                    }
                },
                "required": ["user_id"],
            },
        },
    ]

    # Add allowed_callers for PTC and append code_execution tool
    ptc_tools = copy.deepcopy(tool_definitions)
    for tool in ptc_tools:
        tool["allowed_callers"] = ["code_execution_20250825"]
    ptc_tools.append({
        "type": "code_execution_20250825",
        "name": "code_execution",
    })

    # Map tool names to actual functions
    tool_functions = {
        "get_team_members": get_team_members,
        "get_expenses": get_expenses,
        "get_custom_budget": get_custom_budget,
    }

    yield sse_event("status", {"message": "💻 Running PTC agent with team expense tools..."})

    messages = [{"role": "user", "content": user_input}]
    total_tokens = 0
    container_id = None
    api_counter = 0
    start_time = time.time()

    while True:
        request_params = {
            "model": get_model(),
            "max_tokens": 4000,
            "tools": ptc_tools,
            "messages": messages,
        }

        response = client.beta.messages.create(
            **request_params,
            betas=["advanced-tool-use-2025-11-20"],
            extra_body={"container": container_id} if container_id else None,
        )
        api_counter += 1

        # Track container for stateful execution
        if hasattr(response, "container") and response.container:
            container_id = response.container.id
            yield sse_event("status", {"message": f"📦 Container: {container_id[:16]}..."})

        # Track token usage
        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        if response.stop_reason == "end_turn":
            # Extract final text response
            final_response = next(
                (block.text for block in response.content if isinstance(block, BetaTextBlock)),
                None,
            )
            elapsed = round(time.time() - start_time, 2)
            if final_response:
                yield sse_event("token", {"text": final_response})

            # Traditional tool-calling baseline (hardcoded from notebook runs)
            trad_tokens = 110473
            trad_elapsed = 50.6

            token_reduction = round((trad_tokens - total_tokens) / trad_tokens * 100, 1)
            time_reduction = round((trad_elapsed - elapsed) / trad_elapsed * 100, 1)

            # Send comparison metrics
            yield sse_event("metrics", {
                "comparison": True,
                "rows": [
                    {"metric": "API Calls", "traditional": str(api_counter), "ptc": str(api_counter)},
                    {"metric": "Total Tokens", "traditional": f"{trad_tokens:,}", "ptc": f"{total_tokens:,}"},
                    {"metric": "Elapsed Time (s)", "traditional": f"{trad_elapsed}", "ptc": f"{elapsed}"},
                    {"metric": "Token Reduction", "traditional": "—", "ptc": f"{token_reduction}%"},
                    {"metric": "Time Reduction", "traditional": "—", "ptc": f"{time_reduction}%"},
                ],
            })
            yield sse_event("done", {"message": f"✅ PTC agent complete! ({api_counter} API calls, {total_tokens:,} tokens, {elapsed}s)"})
            return

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for block in response.content:
                if isinstance(block, BetaToolUseBlock):
                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    # Determine caller type (PTC vs direct)
                    caller_type = block.caller.type if block.caller else "direct"

                    if caller_type == "code_execution_20250825":
                        yield sse_event("status", {"message": f"🔧 [PTC] Code called tool: {tool_name}({json.dumps(tool_input)})"})
                    else:
                        yield sse_event("status", {"message": f"🔧 [Direct] Model called tool: {tool_name}({json.dumps(tool_input)})"})

                    # Execute the tool
                    result = tool_functions[tool_name](**tool_input)

                    # Format result
                    if isinstance(result, list) and result and isinstance(result[0], str):
                        content = "\n".join(result)
                    elif isinstance(result, (dict, list)):
                        content = json.dumps(result)
                    else:
                        content = str(result)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": content,
                    })

            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            elapsed = round(time.time() - start_time, 2)
            final_response = next(
                (block.text for block in response.content if isinstance(block, BetaTextBlock)),
                f"Stopped with reason: {response.stop_reason}",
            )
            if final_response:
                yield sse_event("token", {"text": final_response})
            trad_tokens = 110473
            trad_elapsed = 40.6
            token_reduction = round((trad_tokens - total_tokens) / trad_tokens * 100, 1)
            time_reduction = round((trad_elapsed - elapsed) / trad_elapsed * 100, 1)
            yield sse_event("metrics", {
                "comparison": True,
                "rows": [
                    {"metric": "API Calls", "traditional": str(api_counter), "ptc": str(api_counter)},
                    {"metric": "Total Tokens", "traditional": f"{trad_tokens:,}", "ptc": f"{total_tokens:,}"},
                    {"metric": "Elapsed Time (s)", "traditional": f"{trad_elapsed}", "ptc": f"{elapsed}"},
                    {"metric": "Token Reduction", "traditional": "—", "ptc": f"{token_reduction}%"},
                    {"metric": "Time Reduction", "traditional": "—", "ptc": f"{time_reduction}%"},
                ],
            })
            yield sse_event("done", {"message": f"⚠️ Stopped: {response.stop_reason} ({elapsed}s)"})
            return


def run_web_search(user_input: str):
    """Web search – Claude searches the web and answers with citations."""
    client = get_client()

    yield sse_event("status", {"message": "🔍 Claude is searching the web..."})

    response = client.messages.create(
        model=get_model(),
        max_tokens=4096,
        messages=[{"role": "user", "content": user_input}],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }],
    )

    # Extract text blocks from the response
    for block in response.content:
        if hasattr(block, "text"):
            yield sse_event("token", {"text": block.text})

    yield sse_event("done", {"message": "✅ Web search complete!"})


def run_web_fetch(user_input: str):
    """Web fetch – Claude fetches a URL and analyzes its content."""
    client = get_client()

    yield sse_event("status", {"message": "🌐 Claude is fetching the URL..."})

    response = client.messages.create(
        model=get_model(),
        max_tokens=4096,
        messages=[{"role": "user", "content": user_input}],
        tools=[{
            "type": "web_fetch_20250910",
            "name": "web_fetch",
            "max_uses": 3,
        }],
        extra_headers={
            "anthropic-beta": "web-fetch-2025-09-10",
        },
    )

    for block in response.content:
        if hasattr(block, "text"):
            yield sse_event("token", {"text": block.text})

    yield sse_event("done", {"message": "✅ Web fetch complete!"})


def run_generate_docx(user_input: str):
    yield from _run_skill("docx", user_input, "docx")


def run_generate_pdf(user_input: str):
    yield from _run_skill("pdf", user_input, "pdf")


def run_prompt_caching(user_input: str):
    """Run 1-hour prompt caching demo.
    First run records the baseline time. Subsequent runs show cached speedup.
    After the 1-hour TTL expires, the cycle resets.
    """
    global _baseline_time, _baseline_timestamp

    client = get_client()
    content = _ANNUAL_REPORT_CONTENT
    timestamp = str(_CACHE_TIMESTAMP)

    if not content:
        yield sse_event("error", {"message": "Annual Report not loaded. Check uploads folder."})
        yield sse_event("done", {"message": "❌ Missing Annual Report."})
        return

    # Check if previous baseline has expired (1 hour = 3600s)
    if _baseline_timestamp is not None and (time.time() - _baseline_timestamp) >= 3600:
        _baseline_time = None
        _baseline_timestamp = None

    is_first_run = _baseline_time is None

    if is_first_run:
        yield sse_event("status", {"message": "⚡ First run – recording baseline (cache_control=ephemeral, ttl=1h)..."})
    else:
        yield sse_event("status", {"message": "⚡ Running with 1-hour prompt caching (cache_control=ephemeral, ttl=1h)..."})

    cached_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": timestamp + "<book>" + content + "</book>",
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {"type": "text", "text": user_input},
            ],
        }
    ]

    c_start = time.time()
    response = client.messages.create(
        model=get_model(),
        max_tokens=300,
        messages=cached_messages,
    )
    elapsed = round(time.time() - c_start, 2)

    for block in response.content:
        if hasattr(block, "text"):
            yield sse_event("token", {"text": block.text})

    # Build metrics
    usage = response.usage

    if is_first_run:
        _baseline_time = elapsed
        _baseline_timestamp = time.time()
        non_cached_time = elapsed
        cached_time = None
        speedup_str = "—"
    else:
        non_cached_time = _baseline_time
        cached_time = elapsed
        speedup = round(non_cached_time / cached_time, 1) if cached_time > 0 else 0
        speedup_str = f"{speedup}x faster"

    cache_read = getattr(usage, "cache_read_input_tokens", 0)
    cache_create = getattr(usage, "cache_creation_input_tokens", 0)

    if cache_read > 0:
        cache_status = "✅ Cache HIT"
    elif cache_create > 0:
        cache_status = "📝 Cache CREATED"
    else:
        cache_status = "❌ No caching"

    metrics = {
        "cache_type": "1-hour",
        "cache_status": cache_status,
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
        "cache_creation_input_tokens": cache_create,
        "cache_read_input_tokens": cache_read,
        "response_time_seconds": cached_time,
        "non_cached_time_seconds": non_cached_time,
        "speedup": speedup_str,
    }

    yield sse_event("metrics", metrics)


# Map feature id → runner function
FEATURE_RUNNERS = {
    "web_search": run_web_search,
    "web_fetch": run_web_fetch,
    "files_api": run_files_api,
    "code_execution": run_code_execution,
    "prompt_caching": run_prompt_caching,
    "generate_docx": run_generate_docx,
    "generate_pdf": run_generate_pdf,
}


@app.route("/api/run", methods=["POST"])
def run_feature():
    """Run a feature and stream results back via SSE."""
    body = request.json or {}
    feature_id = body.get("featureId")
    user_input = body.get("input", "")

    if feature_id not in FEATURE_RUNNERS:
        return jsonify({"error": f"Unknown feature: {feature_id}"}), 400

    runner = FEATURE_RUNNERS[feature_id]
    upload_key = body.get("uploadKey")

    def generate():
        try:
            if feature_id == "files_api":
                yield from runner(user_input, upload_key=upload_key)
            else:
                yield from runner(user_input)
        except Exception as e:
            yield sse_event("error", {"message": str(e)})
            yield sse_event("done", {"message": f"❌ Error: {e}"})

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/download/<filename>", methods=["GET"])
def download_file(filename):
    """Download a generated file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_file(filepath, as_attachment=True)

# Serve React static files
REACT_BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
print(f"REACT_BUILD path: {REACT_BUILD}")
print(f"REACT_BUILD exists: {os.path.exists(REACT_BUILD)}")
if os.path.exists(REACT_BUILD):
    print(f"REACT_BUILD contents: {os.listdir(REACT_BUILD)}")
    static_sub = os.path.join(REACT_BUILD, "static")
    if os.path.exists(static_sub):
        print(f"static/static contents: {os.listdir(static_sub)}")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    """Serve the React frontend."""
    from flask import send_from_directory
    full_path = os.path.join(REACT_BUILD, path)
    if path and os.path.exists(full_path):
        return send_from_directory(REACT_BUILD, path)
    return send_from_directory(REACT_BUILD, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
