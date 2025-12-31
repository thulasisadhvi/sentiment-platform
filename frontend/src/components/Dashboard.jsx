import React, { useState, useEffect, useRef } from 'react';
import { Activity, MessageSquare, ThumbsUp, ThumbsDown, Minus, Wifi, WifiOff } from 'lucide-react';
import axios from 'axios';

// Import the new Chart Components
import DistributionChart from './DistributionChart';
import SentimentChart from './SentimentChart';

// API Configuration
const API_BASE_URL = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api/ws/sentiment';

// Chart Colors (Still needed for the Live Feed borders)
const COLORS = { positive: '#10B981', negative: '#EF4444', neutral: '#6B7280' };

export default function Dashboard() {
    // --- State Management ---
    const [distributionData, setDistributionData] = useState([]);
    const [trendData, setTrendData] = useState([]);
    const [recentPosts, setRecentPosts] = useState([]);
    const [metrics, setMetrics] = useState({ total: 0, positive: 0, negative: 0, neutral: 0 });
    const [connectionStatus, setConnectionStatus] = useState('connecting');
    const [lastUpdate, setLastUpdate] = useState(new Date());

    const ws = useRef(null);
    const scrollRef = useRef(null);

    // --- Effects ---

    // 1. Fetch Initial Data
    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch Distribution
                const distRes = await axios.get(`${API_BASE_URL}/sentiment/distribution?hours=24`);
                const dist = distRes.data.distribution;
                // Note: We don't strictly need setDistributionData state anymore if we just use metrics,
                // but keeping it for consistency if you expand logic later.
                setDistributionData([
                    { name: 'Positive', value: dist.positive },
                    { name: 'Negative', value: dist.negative },
                    { name: 'Neutral', value: dist.neutral },
                ]);

                // Fetch Trend
                const trendRes = await axios.get(`${API_BASE_URL}/sentiment/aggregate?period=hour`);
                setTrendData(trendRes.data.data.map(item => ({
                    ...item,
                    timestamp: item.timestamp // SentimentChart handles formatting internally
                })));

                // Fetch Recent Posts
                const postsRes = await axios.get(`${API_BASE_URL}/posts?limit=50`);
                setRecentPosts(postsRes.data.posts);

                // Set Initial Metrics
                setMetrics({
                    total: distRes.data.total,
                    positive: dist.positive,
                    negative: dist.negative,
                    neutral: dist.neutral
                });

            } catch (err) {
                console.error("Failed to fetch initial data:", err);
            }
        };

        fetchData();
    }, []);

    // 2. WebSocket Connection
    useEffect(() => {
        const connectWebSocket = () => {
            ws.current = new WebSocket(WS_URL);

            ws.current.onopen = () => {
                setConnectionStatus('connected');
                console.log('Connected to WebSocket');
            };

            ws.current.onclose = () => {
                setConnectionStatus('disconnected');
                setTimeout(connectWebSocket, 3000);
            };

            ws.current.onmessage = (event) => {
                const message = JSON.parse(event.data);
                setLastUpdate(new Date());

                if (message.type === 'new_post') {
                    setRecentPosts(prev => [message.data, ...prev].slice(0, 50));
                } else if (message.type === 'metrics_update') {
                    const data = message.data.last_24_hours;
                    setMetrics(data);
                    // Also update distribution state to keep everything in sync
                    setDistributionData([
                        { name: 'Positive', value: data.positive },
                        { name: 'Negative', value: data.negative },
                        { name: 'Neutral', value: data.neutral },
                    ]);
                }
            };
        };

        connectWebSocket();

        return () => {
            if (ws.current) ws.current.close();
        };
    }, []);

    // --- Layout ---

    return (
        <div className="min-h-screen bg-gray-900 text-white p-6 font-sans">
            <div className="max-w-7xl mx-auto space-y-6">
                
                {/* Header */}
                <header className="flex justify-between items-center bg-gray-800 p-4 rounded-lg shadow-lg">
                    <div>
                        <h1 className="text-2xl font-bold flex items-center gap-2">
                            <Activity className="text-blue-400" />
                            Real-Time Sentiment Dashboard
                        </h1>
                        <p className="text-gray-400 text-sm">Monitoring social media streams</p>
                    </div>
                    <div className="text-right">
                        <div className={`flex items-center justify-end gap-2 ${connectionStatus === 'connected' ? 'text-green-400' : 'text-red-400'}`}>
                            {connectionStatus === 'connected' ? <Wifi size={16} /> : <WifiOff size={16} />}
                            <span className="uppercase font-bold text-xs tracking-wider">{connectionStatus}</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">Last Update: {lastUpdate.toLocaleTimeString()}</p>
                    </div>
                </header>

                {/* Top Row: Distribution & Feed */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    
                    {/* Component 1: Distribution Chart */}
                    <div className="lg:col-span-1">
                        {/* We pass 'metrics' because DistributionChart expects {positive, negative, neutral} */}
                        <DistributionChart data={metrics} />
                    </div>

                    {/* Live Feed */}
                    <div className="bg-gray-800 p-4 rounded-lg shadow-lg lg:col-span-2 flex flex-col h-[24rem]">
                        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                            <MessageSquare size={18} /> Recent Posts
                        </h2>
                        <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-600" ref={scrollRef}>
                            {recentPosts.map((post) => (
                                <div key={post.post_id || Math.random()} className="bg-gray-700 p-3 rounded border-l-4" 
                                     style={{ borderColor: COLORS[post.sentiment?.label || post.sentiment_label] || COLORS.neutral }}>
                                    <div className="flex justify-between items-start mb-1">
                                        <span className="font-bold text-sm text-gray-300">@{post.author}</span>
                                        <span className="text-xs text-gray-500">{new Date(post.created_at || post.timestamp).toLocaleTimeString()}</span>
                                    </div>
                                    <p className="text-sm text-gray-200">{post.content}</p>
                                    <div className="mt-2 flex gap-2 text-xs uppercase tracking-wide opacity-70">
                                        <span className="bg-gray-800 px-2 py-0.5 rounded">{post.source}</span>
                                        <span>{post.sentiment?.label || post.sentiment_label}</span>
                                        <span>{(post.sentiment?.confidence || post.confidence_score)?.toFixed(2)}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Middle Row: Component 2 - Trend Chart */}
                {/* The component itself includes the container styling and title */}
                <SentimentChart data={trendData} />

                {/* Bottom Row: Metrics Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard title="Total Posts" value={metrics.total.toLocaleString()} icon={<MessageSquare className="text-blue-500" />} />
                    <MetricCard title="Positive" value={metrics.positive.toLocaleString()} icon={<ThumbsUp className="text-green-500" />} />
                    <MetricCard title="Negative" value={metrics.negative.toLocaleString()} icon={<ThumbsDown className="text-red-500" />} />
                    <MetricCard title="Neutral" value={metrics.neutral.toLocaleString()} icon={<Minus className="text-gray-500" />} />
                </div>
            </div>
        </div>
    );
}

// Simple sub-component for consistency
function MetricCard({ title, value, icon }) {
    return (
        <div className="bg-gray-800 p-4 rounded-lg shadow-lg flex items-center justify-between border-b-4 border-gray-700 hover:border-blue-500 transition-colors">
            <div>
                <p className="text-gray-400 text-xs uppercase font-bold">{title}</p>
                <p className="text-2xl font-bold mt-1">{value}</p>
            </div>
            <div className="p-3 bg-gray-700 rounded-full bg-opacity-50">
                {icon}
            </div>
        </div>
    );
}