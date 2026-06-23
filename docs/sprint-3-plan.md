# Sprint 3 Plan

## Sprint Goal

Create a simple user interface that allows stakeholders to view cleaned European energy price data and understand pipeline health.

## Recommended Jira Issues

| Issue Type | Summary | Story Points | Priority |
|---|---|---:|---|
| Story | As a user, I want to view average energy prices by country so that I can compare European markets. | 5 | High |
| Story | As a user, I want to filter the dashboard by country so that I can inspect one market at a time. | 3 | High |
| Story | As a stakeholder, I want to see pipeline status so that I know whether the data is reliable. | 3 | Medium |
| Story | As a user, I want to see price trends over time so that I can identify market movement. | 5 | High |
| Task | Build static dashboard page in the app folder. | 3 | Medium |
| Task | Add chart and metric components for Sprint 3 demo. | 3 | Medium |
| Task | Update README with dashboard instructions. | 1 | Medium |
| Bug | Dashboard does not refresh selected country trend after filter change. | 2 | Medium |

## Acceptance Criteria

- Dashboard opens locally in a browser.
- Average price, highest market, record count, and pipeline status are visible.
- Country comparison chart is visible.
- Country filter updates the trend chart.
- UI screenshots can be attached to Jira and the final report.

## Demo Steps

1. Run the Sprint 2 Airflow DAG successfully.
2. Open `app/index.html`.
3. Show the metric cards.
4. Change the country filter.
5. Show the pipeline task progress section.

