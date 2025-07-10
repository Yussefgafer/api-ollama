// server.js (وكيل خارق بمهام متقدمة - بدون jsdom)
const http = require('http');
const axios = require('axios');
const cheerio = require('cheerio');
// const { JSDOM } = require('jsdom'); // <-- تم إزالة هذه المكتبة
const { evaluate } = require('mathjs');
const { google } = require('googleapis');
const fs = require('fs').promises;
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { exec } = require('child_process');

const PORT = process.env.PORT || 3000;
const DUCKDUCKGO_API = 'https://api.duckduckgo.com/?format=json&no_html=1&no_redirect=1';

// ====================================================================
// تهيئة Google Drive API
// ====================================================================
const GOOGLE_CLIENT_EMAIL = process.env.GOOGLE_CLIENT_EMAIL;
const GOOGLE_PRIVATE_KEY = process.env.GOOGLE_PRIVATE_KEY ? process.env.GOOGLE_PRIVATE_KEY.replace(/\\n/g, '\n') : null;

let drive;
if (GOOGLE_CLIENT_EMAIL && GOOGLE_PRIVATE_KEY) {
    const auth = new google.auth.JWT(
        GOOGLE_CLIENT_EMAIL,
        null,
        GOOGLE_PRIVATE_KEY,
        ['https://www.googleapis.com/auth/drive']
    );
    drive = google.drive({ version: 'v3', auth });
    console.log('Google Drive API initialized.');
} else {
    console.warn('Google Drive API credentials not found. Drive tools will not be available.');
}

// ====================================================================
// تخزين المهام
// ====================================================================
const tasks = [];

// ====================================================================
// دالة لمعالجة جميع طلبات JSON-RPC الواردة
// ====================================================================
async function handleRpcRequest(req, res) {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
        let rpcRequest;
        try {
            rpcRequest = JSON.parse(body);
            console.log('\n[Request] استلام طلب RPC:', JSON.stringify(rpcRequest, null, 2));

            let rpcResponse;
            let responseBody;

            switch (rpcRequest.method) {
                case 'initialize':
                    console.log('[Initialize] الخادم يقوم بعملية المصافحة...');
                    const capabilities = {
                        tools: [
                            // أدوات الويب والبحث
                            { name: 'search_web', description: 'Search the web for general information using DuckDuckGo. Use this first to get a broad overview.', inputSchema: { type: 'object", properties: { query: { type: 'string', description: 'The search query.' } }, required: ['query'] } },
                            { name: 'deep_search_web', description: 'Perform a more in-depth web search and extract rich snippets. Useful when a simple search_web is not enough.', inputSchema: { type: 'object", properties: { query: { type: 'string', description: 'The search query for deep search.' } }, required: ['query'] } },
                            { name: 'browse_url', description: 'Visit a specific URL and extract its main text content. Use this to get detailed information from a webpage after a search.', inputSchema: { type: 'object", properties: { url: { type: 'string', description: 'The full URL to browse.' } }, required: ['url'] } },
                            // أدوات الملفات المحلية (على الخادم)
                            { name: 'list_directory', description: 'List all files and subdirectories in a specified path on the server. Default is current directory.', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'Optional: The path to list. Default is current directory (./).' } } } },
                            { name: 'create_file', description: 'Create a new file with specified content at a given path.', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the new file.' }, content: { type: 'string', description: 'The content to write to the file.' } }, required: ['path', 'content'] } },
                            { name: 'read_file', description: 'Read the plain text content of a file at a given path.', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the file.' } }, required: ['path'] } },
                            { name: 'update_file', description: 'Update (overwrite) the content of an existing file at a given path.', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the file to update.' }, content: { type: 'string', description: 'The new content to write to the file.' } }, required: ['path', 'content'] } },
                            { name: 'delete_file', description: 'Delete a file at a given path. Use with extreme caution!', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the file to delete.' } }, required: ['path'] } },
                            { name: 'create_directory', description: 'Create a new directory at a given path.', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the new directory.' } }, required: ['path'] } },
                            { name: 'delete_directory', description: 'Delete an empty directory at a given path. Use with caution!', inputSchema: { type: 'object", properties: { path: { type: 'string', description: 'The path to the directory to delete.' } }, required: ['path'] } },
                            // أدوات Google Drive
                            { name: 'list_drive_files', description: 'List files and folders in Google Drive. Can specify a parent folder ID.', inputSchema: { type: 'object", properties: { parentId: { type: 'string', description: 'Optional: The ID of the parent folder to list from. Default is root.' } } } },
                            { name: 'read_drive_file_content', description: 'Read the plain text content of a Google Drive file by its ID. Only works for text-based files (e.g., .txt, .md, Google Docs).', inputSchema: { type: 'object", properties: { fileId: { type: 'string', description: 'The ID of the Google Drive file to read.' } }, required: ['fileId'] } },
                            // أداة تنفيذ الأوامر الطرفية (خطر أمني)
                            { name: 'execute_command', description: 'Execute a shell command on the server. DANGEROUS! Use ONLY for trusted, essential operations. Output is limited.', inputSchema: { type: 'object", properties: { command: { type: 'string', description: 'The shell command to execute.' } }, required: ['command'] } },
                            // أدوات المرافق
                            { name: 'summarize_text', description: 'Summarize a long piece of text. Useful when you have too much information and need to extract key points.', inputSchema: { type: 'object", properties: { text: { type: 'string', description: 'The text to summarize.' } }, required: ['text'] } },
                            { name: 'get_current_time', description: 'Get the current date and time. Useful when you need up-to-date time information.', inputSchema: { type: 'object", properties: {} } },
                            { name: 'perform_calculation', description: 'Perform a mathematical calculation or evaluate an expression. Useful for complex arithmetic or algebra.', inputSchema: { type: 'object", properties: { expression: { type: 'string', description: 'The mathematical expression to evaluate (e.g., "2 + 3 * 4").' } }, required: ['expression'] } },
                            // أدوات قائمة المهام
                            { name: 'add_task', description: 'Add a new task to the To-Do list.', inputSchema: { type: 'object", properties: { description: { type: 'string', description: 'Description of the task.' } }, required: ['description'] } },
                            { name: 'list_tasks', description: 'List all current tasks (pending and completed).', inputSchema: { type: 'object", properties: {} } },
                            { name: 'complete_task', description: 'Mark a task as completed by its ID.', inputSchema: { type: 'object", properties: { taskId: { type: 'string', description: 'The ID of the task to mark as complete.' } }, required: ['taskId'] } },
                            { name: 'clear_tasks', description: 'Clear all tasks from the To-Do list. Use with caution.', inputSchema: { type: 'object", properties: {} } }
                        ]
                    };

                    rpcResponse = {
                        jsonrpc: '2.0',
                        id: rpcRequest.id,
                        result: {
                            serverInfo: {
                                name: "Super Agent Advanced Tools Server",
                                version: "1.0.0",
                                notes: "Provides advanced web, file, terminal, and utility tools for AI agents."
                            },
                            capabilities: capabilities
                        }
                    };
                    console.log('[Initialize] تم إرسال استجابة المصافحة الكاملة بنجاح.');
                    break;

                case 'callTool':
                    let toolResult;
                    const toolName = rpcRequest.params.name;
                    const args = rpcRequest.params.arguments;

                    console.log(`[Tool Call] طلب تنفيذ أداة: ${toolName}`);

                    switch (toolName) {
                        case 'search_web': /* ... نفس الكود السابق ... */
                            if (!args || !args.query) { throw new Error("Query is missing for search_web."); }
                            toolResult = await searchDuckDuckGo(args.query);
                            break;
                        case 'deep_search_web': /* ... نفس الكود السابق ... */
                            if (!args || !args.query) { throw new Error("Query is missing for deep_search_web."); }
                            toolResult = await deepSearchWeb(args.query);
                            break;
                        case 'browse_url': /* ... نفس الكود السابق ... */
                            if (!args || !args.url) { throw new Error("URL is missing for browse_url."); }
                            toolResult = await browseUrl(args.url);
                            break;
                        case 'list_directory': /* ... نفس الكود السابق ... */
                            toolResult = await listDirectory(args ? args.path : './');
                            break;
                        case 'create_file': /* ... نفس الكود السابق ... */
                            if (!args || !args.path || args.content === undefined) { throw new Error("Path and content are required for create_file."); }
                            toolResult = await createFile(args.path, args.content);
                            break;
                        case 'read_file': /* ... نفس الكود السابق ... */
                            if (!args || !args.path) { throw new Error("Path is required for read_file."); }
                            toolResult = await readFile(args.path);
                            break;
                        case 'update_file': /* ... نفس الكود السابق ... */
                            if (!args || !args.path || args.content === undefined) { throw new Error("Path and content are required for update_file."); }
                            toolResult = await updateFile(args.path, args.content);
                            break;
                        case 'delete_file': /* ... نفس الكود السابق ... */
                            if (!args || !args.path) { throw new Error("Path is required for delete_file."); }
                            toolResult = await deleteFile(args.path);
                            break;
                        case 'create_directory': /* ... نفس الكود السابق ... */
                            if (!args || !args.path) { throw new Error("Path is required for create_directory."); }
                            toolResult = await createDirectory(args.path);
                            break;
                        case 'delete_directory': /* ... نفس الكود السابق ... */
                            if (!args || !args.path) { throw new Error("Path is required for delete_directory."); }
                            toolResult = await deleteDirectory(args.path);
                            break;
                        case 'list_drive_files': /* ... نفس الكود السابق ... */
                            if (!drive) throw new Error("Google Drive API not initialized.");
                            toolResult = await listDriveFiles(args ? args.parentId : null);
                            break;
                        case 'read_drive_file_content': /* ... نفس الكود السابق ... */
                            if (!drive) throw new Error("Google Drive API not initialized.");
                            if (!args || !args.fileId) { throw new Error("File ID is missing for read_drive_file_content."); }
                            toolResult = await readDriveFileContent(args.fileId);
                            break;
                        case 'execute_command': /* ... نفس الكود السابق ... */
                            if (!args || !args.command) { throw new Error("Command is missing for execute_command."); }
                            toolResult = await executeCommand(args.command);
                            break;
                        case 'summarize_text': /* ... نفس الكود السابق ... */
                            if (!args || !args.text) { throw new Error("Text is missing for summarize_text."); }
                            toolResult = await summarizeText(args.text);
                            break;
                        case 'get_current_time': /* ... نفس الكود السابق ... */
                            toolResult = { currentTime: new Date().toISOString() };
                            break;
                        case 'perform_calculation': /* ... نفس الكود السابق ... */
                            if (!args || !args.expression) { throw new Error("Expression is missing for perform_calculation."); }
                            try {
                                const result = evaluate(args.expression);
                                toolResult = { result: result.toString() };
                            } catch (e) {
                                throw new Error(`Invalid expression: ${e.message}`);
                            }
                            break;
                        case 'add_task': /* ... نفس الكود السابق ... */
                            if (!args || !args.description) { throw new Error("Description is required for add_task."); }
                            toolResult = addTask(args.description);
                            break;
                        case 'list_tasks': /* ... نفس الكود السابق ... */
                            toolResult = listTasks();
                            break;
                        case 'complete_task': /* ... نفس الكود السابق ... */
                            if (!args || !args.taskId) { throw new Error("Task ID is required for complete_task."); }
                            toolResult = completeTask(args.taskId);
                            break;
                        case 'clear_tasks': /* ... نفس الكود السابق ... */
                            toolResult = clearTasks();
                            break;
                        default:
                            throw new Error(`Tool '${toolName}' is not supported.`);
                    }

                    rpcResponse = {
                        jsonrpc: '2.0',
                        id: rpcRequest.id,
                        result: toolResult
                    };
                    console.log('[Tool Call] تم إرسال نتائج الأداة بنجاح.');
                    break;

                default:
                    throw new Error(`Method '${rpcRequest.method}' is not supported.`);
            }

            const responseBody = JSON.stringify(rpcResponse);
            res.writeHead(200, {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(responseBody)
            });
            res.end(responseBody);

        } catch (error) {
            console.error('[Error] حدث خطأ أثناء معالجة الطلب:', error.message);
            const errorResponse = {
                jsonrpc: '2.0',
                id: rpcRequest ? rpcRequest.id : null,
                error: { code: -32602, message: 'Invalid Request', data: error.message }
            };
            const errorBody = JSON.stringify(errorResponse);
            res.writeHead(400, {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(errorBody)
            });
            res.end(errorBody);
        }
    });
}

// ====================================================================
// وظائف أدوات الويب والبحث
// ====================================================================

function searchDuckDuckGo(query) {
    return new Promise((resolve, reject) => {
        const searchUrl = `${DUCKDUCKGO_API}&q=${encodeURIComponent(query)}`;
        https.get(searchUrl, {
            headers: { 'User-Agent': 'SuperAgent-MCP-Server/1.0' }
        }, (apiRes) => {
            let data = '';
            apiRes.on('data', (chunk) => data += chunk);
            apiRes.on('end', () => {
                try {
                    const parsedData = JSON.parse(data);
                    const results = (parsedData.RelatedTopics || []).map(item => ({
                        title: item.Text || 'No Title',
                        url: item.FirstURL || '#',
                        snippet: item.Abstract || item.Result || 'No snippet available.'
                    }));
                    resolve({ query: query, results: results.slice(0, 5) });
                } catch (e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

async function deepSearchWeb(query) {
    try {
        const searchUrl = `${DUCKDUCKGO_API}&q=${encodeURIComponent(query)}`;
        const response = await axios.get(searchUrl, {
            headers: { 'User-Agent': 'SuperAgent-MCP-DeepSearch/1.0' }
        });
        const parsedData = response.data;

        let richContent = '';
        if (parsedData.AbstractText) { richContent += `Abstract: ${parsedData.AbstractText}\n`; }
        if (parsedData.AbstractURL) { richContent += `Abstract URL: ${parsedData.AbstractURL}\n`; }
        if (parsedData.RelatedTopics && parsedData.RelatedTopics.length > 0) {
            richContent += '\nRelated Topics:\n';
            parsedData.RelatedTopics.slice(0, 3).forEach((item, index) => {
                richContent += `${index + 1}. Title: ${item.Text || 'N/A'}\n`;
                richContent += `   URL: ${item.FirstURL || 'N/A'}\n`;
                if (item.Abstract) { richContent += `   Snippet: ${item.Abstract}\n`; }
                richContent += '\n';
            });
        }
        if (parsedData.Definition) { richContent += `\nDefinition: ${parsedData.Definition}\n`; }
        const MAX_RICH_CONTENT_LENGTH = 3000;
        if (richContent.length > MAX_RICH_CONTENT_LENGTH) { richContent = richContent.substring(0, MAX_RICH_CONTENT_LENGTH) + '... (truncated)'; }
        return { query: query, richContent: richContent };
    } catch (error) {
        console.error(`Error during deep web search for '${query}': ${error.message}`);
        throw new Error(`Deep web search failed: ${error.message}`);
    }
}

async function browseUrl(url) {
    try {
        const response = await axios.get(url, {
            headers: { 'User-Agent': 'SuperAgent-MCP-Browser/1.0' }
        });
        const html = response.data;
        const $ = cheerio.load(html);

        $('script, style, nav, footer, header, form, iframe, img, svg, audio, video').remove();

        let textContent = $('body').text();
        textContent = textContent.replace(/\s+/g, ' ').trim();
        textContent = textContent.split('.\s*\n').map(s => s.trim()).filter(s => s.length > 10).join('.\n');

        const MAX_TEXT_LENGTH = 2000;
        if (textContent.length > MAX_TEXT_LENGTH) {
            textContent = textContent.substring(0, MAX_TEXT_LENGTH) + '... (truncated)';
        }
        return { url: url, content: textContent };
    } catch (error) {
        console.error(`Error browsing URL ${url}: ${error.message}`);
        return { url: url, error: `Failed to browse URL: ${error.message}. It might be inaccessible or malformed.` };
    }
}

// ====================================================================
// وظائف أدوات الملفات المحلية (على الخادم)
// ====================================================================

function getSafePath(inputPath) {
    const resolvedPath = path.resolve(process.cwd(), inputPath);
    if (!resolvedPath.startsWith(process.cwd())) {
        throw new Error("Access denied: Path outside working directory.");
    }
    return resolvedPath;
}

async function listDirectory(dirPath = './') {
    try {
        const safePath = getSafePath(dirPath);
        const entries = await fs.readdir(safePath, { withFileTypes: true });
        const result = entries.map(entry => ({
            name: entry.name,
            type: entry.isDirectory() ? 'directory' : 'file'
        }));
        return { path: dirPath, contents: result };
    } catch (error) {
        console.error(`Error listing directory ${dirPath}: ${error.message}`);
        throw new Error(`Failed to list directory: ${error.message}`);
    }
}

async function createFile(filePath, content) {
    try {
        const safePath = getSafePath(filePath);
        await fs.writeFile(safePath, content, 'utf8');
        return { status: 'success', message: `File '${filePath}' created.` };
    } catch (error) {
        console.error(`Error creating file ${filePath}: ${error.message}`);
        throw new Error(`Failed to create file: ${error.message}`);
    }
}

async function readFile(filePath) {
    try {
        const safePath = getSafePath(filePath);
        const content = await fs.readFile(safePath, 'utf8');
        const MAX_FILE_CONTENT_LENGTH = 5000;
        const truncatedContent = content.length > MAX_FILE_CONTENT_LENGTH ?
            content.substring(0, MAX_FILE_CONTENT_LENGTH) + '... (truncated)' : content;
        return { path: filePath, content: truncatedContent };
    } catch (error) {
        console.error(`Error reading file ${filePath}: ${error.message}`);
        throw new Error(`Failed to read file: ${error.message}`);
    }
}

async function updateFile(filePath, content) {
    try {
        const safePath = getSafePath(filePath);
        await fs.writeFile(safePath, content, 'utf8');
        return { status: 'success', message: `File '${filePath}' updated.` };
    } catch (error) {
        console.error(`Error updating file ${filePath}: ${error.message}`);
        throw new Error(`Failed to update file: ${error.message}`);
    }
}

async function deleteFile(filePath) {
    try {
        const safePath = getSafePath(filePath);
        await fs.unlink(safePath);
        return { status: 'success', message: `File '${filePath}' deleted.` };
    } catch (error) {
        console.error(`Error deleting file ${filePath}: ${error.message}`);
        throw new Error(`Failed to delete file: ${error.message}`);
    }
}

async function createDirectory(dirPath) {
    try {
        const safePath = getSafePath(dirPath);
        await fs.mkdir(safePath, { recursive: true });
        return { status: 'success', message: `Directory '${dirPath}' created.` };
    } catch (error) {
        console.error(`Error creating directory ${dirPath}: ${error.message}`);
        throw new Error(`Failed to create directory: ${error.message}`);
    }
}

async function deleteDirectory(dirPath) {
    try {
        const safePath = getSafePath(dirPath);
        await fs.rmdir(safePath);
        return { status: 'success', message: `Directory '${dirPath}' deleted.` };
    } catch (error) {
        console.error(`Error deleting directory ${dirPath}: ${error.message}`);
        throw new Error(`Failed to delete directory: ${error.message}. Make sure it's empty.`);
    }
}

// ====================================================================
// وظيفة تنفيذ الأوامر الطرفية (خطر أمني كبير)
// ====================================================================
async function executeCommand(command) {
    console.warn(`[SECURITY WARNING] Attempting to execute command: ${command}`);
    const MAX_COMMAND_OUTPUT_LENGTH = 1000;

    return new Promise((resolve, reject) => {
        exec(command, { timeout: 10000 }, (error, stdout, stderr) => {
            if (error) {
                console.error(`Error executing command: ${error.message}`);
                reject(new Error(`Command failed: ${error.message}. Stderr: ${stderr.substring(0, MAX_COMMAND_OUTPUT_LENGTH)}`));
                return;
            }
            if (stderr) {
                console.warn(`Command stderr: ${stderr.substring(0, MAX_COMMAND_OUTPUT_LENGTH)}`);
            }
            let output = stdout || stderr;
            if (output.length > MAX_COMMAND_OUTPUT_LENGTH) {
                output = output.substring(0, MAX_COMMAND_OUTPUT_LENGTH) + '... (truncated)';
            }
            resolve({ status: 'success', output: output });
        });
    });
}

// ====================================================================
// وظائف أدوات Google Drive
// ====================================================================
async function listDriveFiles(parentId = 'root') {
    try {
        const res = await drive.files.list({
            q: `'${parentId}' in parents and trashed=false`,
            fields: 'files(id, name, mimeType, modifiedTime)',
            pageSize: 10
        });
        const files = res.data.files.map(file => ({
            id: file.id,
            name: file.name,
            type: file.mimeType.includes('folder') ? 'folder' : 'file',
            modifiedTime: file.modifiedTime
        }));
        return { files: files };
    } catch (error) {
        console.error('Error listing Drive files:', error.message);
        throw new Error(`Failed to list Drive files: ${error.message}`);
    }
}

async function readDriveFileContent(fileId) {
    try {
        const fileMetadata = await drive.files.get({ fileId: fileId, fields: 'mimeType, name' });
        const mimeType = fileMetadata.data.mimeType;
        const fileName = fileMetadata.data.name;

        const readableMimeTypes = [
            'text/plain', 'text/html', 'text/css', 'text/javascript', 'application/json',
            'application/xml', 'text/markdown', 'application/vnd.google-apps.document',
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.google-apps.presentation'
        ];

        if (!readableMimeTypes.some(type => mimeType.includes(type))) {
            throw new Error(`File type '${mimeType}' for file '${fileName}' is not a readable text format.`);
        }

        const res = await drive.files.export({ fileId: fileId, mimeType: 'text/plain' }, { responseType: 'stream' });
        let content = '';
        await new Promise((resolve, reject) => {
            res.data.on('data', chunk => content += chunk);
            res.data.on('end', resolve);
            res.data.on('error', reject);
        });

        const MAX_CONTENT_LENGTH = 5000;
        if (content.length > MAX_CONTENT_LENGTH) {
            content = content.substring(0, MAX_CONTENT_LENGTH) + '... (truncated)';
        }

        return { fileId: fileId, fileName: fileName, content: content };
    } catch (error) {
        console.error(`Error reading Drive file ${fileId}:`, error.message);
        throw new Error(`Failed to read Drive file content: ${error.message}`);
    }
}

// ====================================================================
// وظائف أدوات المرافق وقائمة المهام
// ====================================================================

async function summarizeText(text) {
    const MAX_SUMMARY_INPUT_LENGTH = 1000;
    let processedText = text;
    if (text.length > MAX_SUMMARY_INPUT_LENGTH) {
        processedText = text.substring(0, MAX_SUMMARY_INPUT_LENGTH) + '... (truncated for summary)';
    }
    return { originalLength: text.length, processedLength: processedText.length, textForSummary: processedText };
}

const tasks = []; // قائمة بسيطة لتخزين المهام

function addTask(description) {
    const newTask = {
        id: uuidv4(),
        description: description,
        completed: false,
        createdAt: new Date().toISOString()
    };
    tasks.push(newTask);
    return { status: 'success', message: 'Task added.', task: newTask };
}

function listTasks() {
    return { tasks: tasks };
}

function completeTask(taskId) {
    const taskIndex = tasks.findIndex(task => task.id === taskId);
    if (taskIndex !== -1) {
        tasks[taskIndex].completed = true;
        tasks[taskIndex].completedAt = new Date().toISOString();
        return { status: 'success', message: 'Task marked as complete.', task: tasks[taskIndex] };
    }
    throw new Error("Task not found.");
}

function clearTasks() {
    tasks.length = 0;
    return { status: 'success', message: 'All tasks cleared.' };
}

// ====================================================================
// إنشاء وبدء الخادم (بدون تغيير)
// ====================================================================
const server = http.createServer((req, res) => {
    if (req.url === '/' && req.method === 'POST') {
        handleRpcRequest(req, res);
    } else {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not Found', message: 'This server only accepts POST requests at the root path (/).' }));
    }
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`خادم وكيل الويب الخارق يعمل الآن على المنفذ: ${PORT}`);
    console.log('الخادم جاهز لاستقبال طلبات POST على المسار الرئيسي "/".');
});

process.on('SIGINT', () => {
    console.log('إغلاق الخادم...');
    server.close(() => {
        console.log('تم إغلاق الخادم بنجاح.');
        process.exit(0);
    });
});