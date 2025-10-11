import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const BASE_URL = __ENV.GATEWAY_BASE_URL || 'http://localhost:8000';
const VUS = Number(__ENV.K6_VUS || 10);
const DURATION = __ENV.K6_DURATION || '1m';

const latencyTrend = new Trend('gateway_latency_duration', true);
const errorRate = new Rate('gateway_request_errors');

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_duration: ['p(95)<150'],
    http_req_failed: ['rate<0.05'],
    gateway_latency_duration: ['p(95)<150'],
    gateway_request_errors: ['rate<0.02'],
  },
};

function request(path, params = {}) {
  const response = http.get(`${BASE_URL}${path}`, params);
  latencyTrend.add(response.timings.duration);
  errorRate.add(response.status >= 500 || response.status === 0);

  check(response, {
    [`${path} responded 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });

  return response;
}

export default function gatewayLatencySmoke() {
  const markets = ['wecc', 'miso', 'ercot'];
  const market = markets[Math.floor(Math.random() * markets.length)];

  request('/api/v1/programs/ra', { params: { market } });
  request('/api/v1/programs/rps', {
    params: { market, compliance_year: 2024 },
  });
  request('/api/v1/programs/ghg', {
    params: { market, scope: 'scope1' },
  });

  sleep(1);
}
