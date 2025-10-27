'use client';

import useSWR from 'swr';
import { api } from '@/lib/api';

export default function HealthBadge() {
  const { data, error } = useSWR('health', api.getHealth, {
    refreshInterval: 30000,
  });

  const isHealthy = data?.status === 'ok';
  const status = error ? 'error' : isHealthy ? 'healthy' : 'unknown';

  return (
    <div className="flex items-center gap-2">
      <div
        className={`w-2 h-2 rounded-full ${
          status === 'healthy'
            ? 'bg-green-500'
            : status === 'error'
            ? 'bg-red-500'
            : 'bg-yellow-500'
        }`}
      />
      <span className="text-sm text-gray-600 dark:text-gray-400">
        {status === 'healthy' ? 'API Online' : 'API Offline'}
      </span>
    </div>
  );
}
