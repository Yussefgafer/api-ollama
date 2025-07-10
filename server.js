// server.js (وكيل الويب الخارق بـ MCP)
const http = require('http');
const axios = require('axios'); // لتصفح الويب
const cheerio = require('cheerio'); // لتحليل HTML
const { JSDOM } = require('jsdom'); // لتنظيف HTML
const { evaluate } = require('mathjs'); // لإجراء العمليات الحسابية

const PORT = process.env.PORT || 3000; // استخدم منفذ البيئة للاستضافة السحابية
const DUCKDUCKGO_API = 'https://api.duckduckgo.com/?format=json&no_html=1&no_redirect=1';

// دالة لمعالجة جميع طلبات JSON-RPC الواردة
async function handleRpcRequest(req, res) {
    let body = '';
    req.on('data', chunk => {
        body += chunk.toString();
    });

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
                            {
                                name: 'search_web',
                                description: 'Search the web for information using DuckDuckGo. Useful for finding general information, news, or answers to factual questions.',
                                inputSchema: {
                                    type: 'object",
                                    properties: { query: { type: 'string', description: 'The search query.' } },
                                    required: ['query']
                                }
                            },
                            {
                                name: 'browse_url',
                                description: 'Visit a specific URL and extract its main text content. Use this to get detailed information from a webpage after a search.',
                                inputSchema: {
                                    type: 'object",
                                    properties: { url: { type: 'string', description: 'The full URL to browse.' } },
                                    required: ['url']
                                }
                            },
                            {
                                name: 'summarize_text',
                                description: 'Summarize a long piece of text. Useful when you have too much information and need to extract key points.',
                                inputSchema: {
                                    type: 'object",
                                    properties: { text: { type: 'string', description: 'The text to summarize.' } },
                                    required: ['text']
                                }
                            },
                            {
                                name: 'get_current_time',
                                description: 'Get the current date and time. Useful when you need up-to-date time information.',
                                inputSchema: { type: 'object', properties: {} }
                            },
                            {
                                name: 'perform_calculation',
                                description: 'Perform a mathematical calculation or evaluate an expression. Useful for complex arithmetic or algebra.',
                                inputSchema: {
                                    type: 'object",
                                    properties: { expression: { type: 'string', description: 'The mathematical expression to evaluate (e.g., "2 + 3 * 4").' } },
                                    required: ['expression']
                                }
                            }
                        ]
                    };

                    rpcResponse = {
                        jsonrpc: '2.0',
                        id: rpcRequest.id,
                        result: {
                            serverInfo: {
                                name: "Super Agent Web & Utils Server",
                                version: "1.0.0",
                                notes: "Provides web browsing, search, and utility tools for advanced AI agents."
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
                        case 'search_web':
                            if (!args || !args.query) { throw new Error("Query is missing for search_web."); }
                            toolResult = await searchDuckDuckGo(args.query);
                            break;
                        case 'browse_url':
                            if (!args || !args.url) { throw new Error("URL is missing for browse_url."); }
                            toolResult = await browseUrl(args.url);
                            break;
                        case 'summarize_text':
                            if (!args || !args.text) { throw new Error("Text is missing for summarize_text."); }
                            toolResult = await summarizeText(args.text); // يعتمد على النموذج نفسه
                            break;
                        case 'get_current_time':
                            toolResult = { currentTime: new Date().toISOString() };
                            break;
                        case 'perform_calculation':
                            if (!args || !args.expression) { throw new Error("Expression is missing for perform_calculation."); }
                            try {
                                const result = evaluate(args.expression);
                                toolResult = { result: result.toString() }; // تحويل النتيجة إلى سلسلة نصية
                            } catch (e) {
                                throw new Error(`Invalid expression: ${e.message}`);
                            }
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

// إنشاء الخادم
const server = http.createServer((req, res) => {
    if (req.url === '/' && req.method === 'POST') {
        handleRpcRequest(req, res);
    } else {
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not Found', message: 'This server only accepts POST requests at the root path (/).' }));
    }
});

// وظيفة البحث في DuckDuckGo
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
                    // تحويل نتائج DuckDuckGo إلى تنسيق أكثر قابلية للاستخدام للنموذج
                    const results = (parsedData.RelatedTopics || []).map(item => ({
                        title: item.Text || 'No Title',
                        url: item.FirstURL || '#',
                        snippet: item.Abstract || item.Result || 'No snippet available.'
                    }));
                    resolve({ query: query, results: results.slice(0, 5) }); // حد 5 نتائج
                } catch (e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

// وظيفة تصفح URL واستخراج النص الرئيسي
async function browseUrl(url) {
    try {
        const response = await axios.get(url, {
            headers: { 'User-Agent': 'SuperAgent-MCP-Browser/1.0' }
        });
        const html = response.data;
        const $ = cheerio.load(html);

        // إزالة العناصر غير المرغوب فيها (script, style, nav, footer, header)
        $('script, style, nav, footer, header, form, iframe, img, svg, audio, video').remove();

        // استخراج النص من جسم الصفحة
        let textContent = $('body').text();

        // تنظيف النص: إزالة المسافات البيضاء الزائدة والأسطر الفارغة
        textContent = textContent.replace(/\s+/g, ' ').trim(); // استبدال مسافات متعددة بمسافة واحدة
        textContent = textContent.split('.\s*\n').map(s => s.trim()).filter(s => s.length > 10).join('.\n'); // تقسيم وإعادة ربط لتقليل الأسطر الفارغة

        // الحد من طول النص لتجنب تجاوز حد الرموز للنموذج
        const MAX_TEXT_LENGTH = 2000; // يمكن تعديلها
        if (textContent.length > MAX_TEXT_LENGTH) {
            textContent = textContent.substring(0, MAX_TEXT_LENGTH) + '... (truncated)';
        }

        return { url: url, content: textContent };
    } catch (error) {
        console.error(`Error browsing URL ${url}: ${error.message}`);
        // إرجاع رسالة خطأ واضحة للنموذج
        return { url: url, error: `Failed to browse URL: ${error.message}. It might be inaccessible or malformed.` };
    }
}

// وظيفة تلخيص النص (هذه وظيفة وهمية، النموذج هو من سيقوم بالتلخيص)
async function summarizeText(text) {
    // في الواقع، النموذج اللغوي هو من سيقوم بالتلخيص بناءً على طلبك
    // هذه الأداة تخبر النموذج فقط أنه يمكنه "طلب" تلخيص نص.
    // النموذج سيتلقى النص ثم يستخدم قدراته الخاصة لتلخيصه.
    // يمكننا هنا إرجاع النص كما هو أو جزء منه كإشارة.
    const MAX_SUMMARY_INPUT_LENGTH = 1000; // الحد الأقصى للنص الذي يمكن أن يتعامل معه النموذج
    let processedText = text;
    if (text.length > MAX_SUMMARY_INPUT_LENGTH) {
        processedText = text.substring(0, MAX_SUMMARY_INPUT_LENGTH) + '... (truncated for summary)';
    }
    return { originalLength: text.length, processedLength: processedText.length, textForSummary: processedText };
}


// بدء تشغيل الخادم
server.listen(PORT, '0.0.0.0', () => { // الاستماع على '0.0.0.0' للسماح بالوصول من الخارج في الاستضافة السحابية
    console.log(`خادم وكيل الويب الخارق يعمل الآن على المنفذ: ${PORT}`);
    console.log('الخادم جاهز لاستقبال طلبات POST على المسار الرئيسي "/".');
});

// إغلاق الخادم
process.on('SIGINT', () => {
    console.log('إغلاق الخادم...');
    server.close(() => {
        console.log('تم إغلاق الخادم بنجاح.');
        process.exit(0);
    });
});