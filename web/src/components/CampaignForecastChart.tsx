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
  // Group data by insertion month for timeline view
  const monthlyData = forecastData.reduce((acc, item) => {
    const monthKey = item.insertion_month_start;
    if (!acc[monthKey]) {
      acc[monthKey] = {
        month: monthKey,
        clicks: 0,
        spend: 0,
        placements: 0,
        creators: new Set(),
      };
    }
    acc[monthKey].clicks += item.forecasted_clicks;
    acc[monthKey].spend += item.forecasted_spend;
    acc[monthKey].placements += 1;
    acc[monthKey].creators.add(item.creator_name);
    return acc;
  }, {} as Record<string, { month: string; clicks: number; spend: number; placements: number; creators: Set<string> }>);

  // Sort by month
  const sortedMonths = Object.values(monthlyData).sort((a, b) => 
    new Date(a.month).getTime() - new Date(b.month).getTime()
  );

  const chartData = {
    labels: sortedMonths.map(item => {
      const date = new Date(item.month);
      return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    }),
    datasets: [
      {
        label: 'Forecasted Clicks',
        data: sortedMonths.map(item => item.clicks),
        borderColor: 'rgb(59, 130, 246)', // blue-500
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        borderWidth: 3,
        fill: true,
        tension: 0.4,
        yAxisID: 'y',
      },
      {
        label: 'Forecasted Spend ($)',
        data: sortedMonths.map(item => item.spend),
        borderColor: 'rgb(34, 197, 94)', // green-500
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        borderWidth: 3,
        fill: false,
        tension: 0.4,
        yAxisID: 'y1',
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      title: {
        display: true,
        text: `${campaignName} - Performance Forecast`,
        font: {
          size: 18,
          weight: 'bold' as const,
        },
        color: '#374151', // gray-700
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
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: 'white',
        bodyColor: 'white',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        cornerRadius: 8,
        displayColors: true,
        callbacks: {
          title: (context: any) => {
            const dataIndex = context[0].dataIndex;
            const monthData = sortedMonths[dataIndex];
            return `${monthData.month} (${monthData.placements} placements)`;
          },
          afterTitle: (context: any) => {
            const dataIndex = context[0].dataIndex;
            const monthData = sortedMonths[dataIndex];
            const creatorList = Array.from(monthData.creators).join(', ');
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
          text: 'Month',
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
          text: 'Clicks',
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
          text: 'Spend ($)',
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
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="mb-6">
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
      
      <div className="h-96">
        <Line data={chartData} options={options} />
      </div>
      
      <div className="mt-4 text-xs text-gray-500 text-center">
        Forecast based on historical performance data and conservative estimates
      </div>
    </div>
  );
};
