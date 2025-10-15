import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { CampaignForecastData } from '../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface CampaignForecastChartProps {
  forecastData: CampaignForecastData[];
  campaignName: string;
  totalForecastedSpend: number;
  totalForecastedClicks: number;
}

export const CampaignForecastChart: React.FC<CampaignForecastChartProps> = ({
  forecastData,
  campaignName,
  totalForecastedSpend,
  totalForecastedClicks,
}) => {
  // Group data by execution date for timeline view
  const dailyData = forecastData.reduce((acc, item) => {
    const dateKey = item.execution_date;
    if (!acc[dateKey]) {
      acc[dateKey] = {
        date: dateKey,
        clicks: 0,
        spend: 0,
        placements: 0,
        creators: new Set(),
      };
    }
    acc[dateKey].clicks += item.forecasted_clicks;
    acc[dateKey].spend += item.forecasted_spend;
    acc[dateKey].placements += 1;
    acc[dateKey].creators.add(item.creator_name);
    return acc;
  }, {} as Record<string, { date: string; clicks: number; spend: number; placements: number; creators: Set<string> }>);

  // Sort by date
  const sortedDates = Object.values(dailyData).sort((a, b) => 
    new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  // Calculate cumulative spend
  let cumulativeSpend = 0;
  const cumulativeData = sortedDates.map(item => {
    cumulativeSpend += item.spend;
    return {
      ...item,
      cumulativeSpend
    };
  });

  const chartData = {
    labels: cumulativeData.map(item => {
      const date = new Date(item.date);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }),
    datasets: [
      {
        label: 'Daily Spend ($)',
        data: cumulativeData.map(item => item.spend),
        borderColor: 'rgb(34, 197, 94)', // green-500
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        yAxisID: 'y1',
      },
      {
        label: 'Cumulative Spend ($)',
        data: cumulativeData.map(item => item.cumulativeSpend),
        borderColor: 'rgb(59, 130, 246)', // blue-500
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        yAxisID: 'y',
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'nearest' as const,
      intersect: false,
      axis: 'x' as const,
    },
    plugins: {
      title: {
        display: true,
        text: `${campaignName} - Cumulative Revenue Forecast`,
        font: {
          size: 20,
          weight: 'bold' as const,
        },
        color: '#1F2937', // gray-800
        padding: {
          top: 20,
          bottom: 30
        }
      },
      legend: {
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 20,
          font: {
            size: 12,
            weight: 'normal' as const,
          },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: 'white',
        bodyColor: 'white',
        borderColor: 'rgba(255, 255, 255, 0.2)',
        borderWidth: 1,
        cornerRadius: 12,
        displayColors: true,
        padding: 12,
        titleFont: {
          size: 14,
          weight: 'bold' as const
        },
        bodyFont: {
          size: 12,
          weight: 'normal' as const
        },
        maxWidth: 300,
        callbacks: {
          title: (context: any) => {
            const dataIndex = context[0].dataIndex;
            const dateData = cumulativeData[dataIndex];
            return `${dateData.date} (${dateData.placements} placements)`;
          },
          afterTitle: (context: any) => {
            const dataIndex = context[0].dataIndex;
            const dateData = cumulativeData[dataIndex];
            const creatorList = Array.from(dateData.creators).join(', ');
            return [`Creators: ${creatorList}`];
          },
          label: (context: any) => {
            const label = context.dataset.label;
            const value = context.parsed.y;
            if (label.includes('Spend')) {
              return `${label}: $${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
            return `${label}: ${value.toLocaleString()}`;
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
        title: {
          display: true,
          text: 'Execution Date',
          font: {
            size: 12,
            weight: 'normal' as const,
          },
          color: '#6B7280', // gray-500
        },
        grid: {
          display: false,
        },
        ticks: {
          color: '#6B7280', // gray-500
          font: {
            size: 11,
          },
        },
      },
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: 'Cumulative Spend ($)',
          font: {
            size: 12,
            weight: 'normal' as const,
          },
          color: '#3B82F6', // blue-500
        },
        grid: {
          color: 'rgba(107, 114, 128, 0.1)',
        },
        ticks: {
          color: '#6B7280', // gray-500
          font: {
            size: 11,
          },
          callback: (value: any) => value.toLocaleString(),
        },
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        title: {
          display: true,
          text: 'Daily Spend ($)',
          font: {
            size: 12,
            weight: 'normal' as const,
          },
          color: '#22C55E', // green-500
        },
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          color: '#6B7280', // gray-500
          font: {
            size: 11,
          },
          callback: (value: any) => `$${value.toLocaleString()}`,
        },
      },
    },
  };

  if (forecastData.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="text-center">
          <div className="text-gray-500 text-lg mb-2">No forecast data available</div>
          <div className="text-gray-400 text-sm">Select a campaign to view performance forecast</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-8">
      <div className="mb-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="text-blue-600 text-sm font-medium">Total Forecasted Clicks</div>
            <div className="text-blue-900 text-2xl font-bold">{totalForecastedClicks.toLocaleString()}</div>
          </div>
          <div className="bg-green-50 rounded-lg p-4">
            <div className="text-green-600 text-sm font-medium">Total Forecasted Spend</div>
            <div className="text-green-900 text-2xl font-bold">${totalForecastedSpend.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
          </div>
          <div className="bg-purple-50 rounded-lg p-4">
            <div className="text-purple-600 text-sm font-medium">Total Placements</div>
            <div className="text-purple-900 text-2xl font-bold">{forecastData.length}</div>
          </div>
        </div>
      </div>
      
      <div className="bg-gray-50 rounded-lg p-4 mb-6">
        <div className="h-[600px] w-full">
          <Line data={chartData} options={options} />
        </div>
      </div>
      
      <div className="mt-6 text-sm text-gray-600 text-center bg-gray-50 rounded-lg py-3">
        <strong>Forecast Methodology:</strong> Based on historical performance data and conservative estimates
      </div>
    </div>
  );
};
