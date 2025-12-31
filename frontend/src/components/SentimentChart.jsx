import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Exact colors from requirements
const COLORS = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#6b7280'
};

export default function SentimentChart({ data }) {
    // Handle empty data
    if (!data || data.length === 0) {
        return (
            <div className="bg-gray-800 rounded-lg p-4 h-80 flex flex-col justify-center items-center">
                <h3 className="text-lg font-semibold mb-4 text-white">Sentiment Trend (Last 24 Hours)</h3>
                <p className="text-gray-500">No trend data available</p>
            </div>
        );
    }

    // Format timestamps for X-Axis (ISO -> HH:MM)
    const formattedData = data.map(item => {
        const date = new Date(item.timestamp);
        return {
            ...item,
            time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
    });

    return (
        <div className="bg-gray-800 rounded-lg p-4 h-80 flex flex-col">
            <h3 className="text-lg font-semibold mb-4 text-white">Sentiment Trend (Last 24 Hours)</h3>
            <div className="flex-1">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={formattedData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis 
                            dataKey="time" 
                            stroke="#9ca3af" 
                            tick={{ fontSize: 12 }}
                            minTickGap={30}
                        />
                        <YAxis stroke="#9ca3af" tick={{ fontSize: 12 }} />
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem', color: '#fff' }}
                            labelStyle={{ color: '#9ca3af' }}
                        />
                        <Legend />
                        
                        {/* Lines for each sentiment */}
                        <Line 
                            type="monotone" 
                            dataKey="positive_count" 
                            name="Positive"
                            stroke={COLORS.positive} 
                            strokeWidth={2} 
                            dot={false}
                            activeDot={{ r: 6 }} 
                        />
                        <Line 
                            type="monotone" 
                            dataKey="negative_count" 
                            name="Negative"
                            stroke={COLORS.negative} 
                            strokeWidth={2} 
                            dot={false} 
                            activeDot={{ r: 6 }}
                        />
                        <Line 
                            type="monotone" 
                            dataKey="neutral_count" 
                            name="Neutral"
                            stroke={COLORS.neutral} 
                            strokeWidth={2} 
                            dot={false} 
                            activeDot={{ r: 6 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}