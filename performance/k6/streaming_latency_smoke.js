import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const BASE_URL = __ENV.STREAMING_BASE_URL || 'http://localhost:8001';
const VUS = Number(__ENV.K6_VUS || 6);
const DURATION = __ENV.K6_DURATION || '1m';

const latencyTrend = new Trend('streaming_http_latency', true);
const errorRate = new Rate('streaming_request_errors');

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_duration: ['p(95)<250'],
    http_req_failed: ['rate<0.05'],
    streaming_http_latency: ['p(95)<250'],
    streaming_request_errors: ['rate<0.02'],
  },
};

function request(path, params) {
  const response = http.get(`${BASE_URL}${path}`, params);
  latencyTrend.add(response.timings.duration);
  errorRate.add(response.status >= 500 || response.status === 0);

  check(response, {
    [`${path} responded 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });

  return response;
}

export default function streamingLatencySmoke() {
  request('/');
  request('/ws/stream');
  request('/stats');

  sleep(1);
}
