import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = {
  Positive: '#10b981', // Green
  Negative: '#ef4444', // Red
  Neutral: '#6b7280'   // Gray
};

export default function DistributionChart({ data }) {
    // Transform data object {positive: 10, ...} into Recharts array format
    const chartData = [
        { name: 'Positive', value: data.positive || 0 },
        { name: 'Negative', value: data.negative || 0 },
        { name: 'Neutral', value: data.neutral || 0 },
    ].filter(item => item.value > 0); // Hide zero values

    const total = chartData.reduce((sum, item) => sum + item.value, 0);

    // Custom Legend to show percentages
    const renderLegend = (props) => {
        const { payload } = props;
        return (
            <ul className="flex justify-center gap-4 mt-4 text-sm">
                {payload.map((entry, index) => {
                    const value = chartData.find(d => d.name === entry.value)?.value || 0;
                    const percent = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                    return (
                        <li key={`item-${index}`} className="flex items-center gap-2">
                            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }}></span>
                            <span className="text-gray-300">{entry.value}: {value} ({percent}%)</span>
                        </li>
                    );
                })}
            </ul>
        );
    };

    if (total === 0) {
        return (
            <div className="bg-gray-800 rounded-lg p-4 h-80 flex flex-col justify-center items-center">
                <h3 className="text-lg font-semibold mb-2 text-white">Sentiment Distribution</h3>
                <p className="text-gray-500">No data available yet</p>
            </div>
        );
    }

    return (
        <div className="bg-gray-800 rounded-lg p-4 h-80 flex flex-col">
            <h3 className="text-lg font-semibold mb-2 text-white">Sentiment Distribution</h3>
            <div className="flex-1">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={80}
                            paddingAngle={5}
                            dataKey="value"
                        >
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[entry.name]} />
                            ))}
                        </Pie>
                        <Tooltip 
                            contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: '0.5rem', color: '#fff' }}
                            itemStyle={{ color: '#fff' }}
                        />
                        <Legend content={renderLegend} />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}