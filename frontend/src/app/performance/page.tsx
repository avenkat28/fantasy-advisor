"use client";
import { useCallback } from "react";
import { Info, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import { MetricsChart } from "@/components/charts";
import {
  EmptyState,
  ErrorState,
  Loading,
  NumberValue,
  PageHeading,
  Panel,
  Stat,
} from "@/components/ui";
export default function PerformancePage() {
  const result = useResource(
    useCallback((signal: AbortSignal) => api.performance(signal), []),
  );
  const data = result.data;
  const models = data?.metrics.filter((m) => m.model === "xgboost");
  return (
    <>
      <PageHeading
        eyebrow="TRANSPARENCY BY DESIGN"
        title="Trust the evidence."
        description="See how the models performed on held-out games, including comparisons against simpler baselines."
        action={
          <span className="tag">
            <ShieldCheck size={14} /> HELD-OUT TEST
          </span>
        }
      />
      {result.loading ? (
        <Loading label="Loading actual model evaluation results…" />
      ) : result.error ? (
        <ErrorState error={result.error} retry={result.retry} />
      ) : !data?.available || !data.metrics.length ? (
        <EmptyState
          title="Evaluation artifacts unavailable"
          message={
            data?.message ||
            "Train and evaluate the models to publish actual test results."
          }
        />
      ) : (
        <>
          <div className="stats-grid">
            <Stat
              label="RB · XGBOOST TEST MAE"
              value={
                <>
                  <NumberValue
                    value={models?.find((m) => m.position === "RB")?.mae}
                    digits={2}
                  />
                  <small> PPR</small>
                </>
              }
              note="Mean absolute error · held-out games"
              accent
            />
            <Stat
              label="WR · XGBOOST TEST MAE"
              value={
                <>
                  <NumberValue
                    value={models?.find((m) => m.position === "WR")?.mae}
                    digits={2}
                  />
                  <small> PPR</small>
                </>
              }
              note="Mean absolute error · held-out games"
            />
            <Stat
              label="MODEL VERSION"
              value={
                <span className="version-value">
                  {data.model_version || "Unavailable"}
                </span>
              }
              note="Separate position-specific models"
            />
          </div>
          <div className="two-columns performance-columns">
            <Panel
              title="The baseline comparison"
              subtitle="Mean absolute error by model · lower is better"
            >
              <MetricsChart metrics={data.metrics} />
            </Panel>
            <Panel
              title="What does MAE mean?"
              subtitle="A useful measure of typical prediction error"
            >
              <div className="explanation">
                <span className="explanation-symbol">±</span>
                <h3>Points away from reality.</h3>
                <p>
                  MAE averages the absolute difference between predicted and
                  actual PPR points across test games. A smaller value means
                  predictions were closer on average.
                </p>
                <p>
                  It is not a confidence interval and does not tell you how
                  accurate one player’s projection will be. RMSE puts more
                  weight on large misses; bias shows whether predictions run
                  high or low.
                </p>
              </div>
            </Panel>
          </div>
          <Panel
            title="Every model. Every metric."
            subtitle="Actual persisted evaluation artifacts from Task 3"
          >
            <div
              className="table-scroll"
              tabIndex={0}
              aria-label="Scrollable historical evaluation metrics"
            >
              <table>
                <caption className="sr-only">
                  Held-out model evaluation by position and baseline
                </caption>
                <thead>
                  <tr>
                    {["Position", "Model", "MAE ↓", "RMSE ↓", "R²", "Bias"].map(
                      (c) => (
                        <th key={c} scope="col">
                          {c}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {data.metrics.map((m) => (
                    <tr
                      key={`${m.position}-${m.model}`}
                      className={m.model === "xgboost" ? "highlight-row" : ""}
                    >
                      <td>{m.position}</td>
                      <td>
                        <strong>{m.model}</strong>
                        {m.model === "xgboost" && (
                          <span className="model-pill">PREDICTION MODEL</span>
                        )}
                      </td>
                      <td>
                        <NumberValue value={m.mae} digits={3} />
                      </td>
                      <td>
                        <NumberValue value={m.rmse} digits={3} />
                      </td>
                      <td>
                        <NumberValue value={m.r2} digits={3} />
                      </td>
                      <td>
                        <NumberValue value={m.bias} digits={3} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel
            title="The evaluation timeline"
            subtitle="Chronological splits keep future games out of training"
          >
            <div className="timeline">
              {Object.entries(data.periods).map(([period, description], i) => (
                <div key={period}>
                  <span className="timeline-number">0{i + 1}</span>
                  <div className="eyebrow">{period.toUpperCase()}</div>
                  <strong>{description}</strong>
                </div>
              ))}
            </div>
          </Panel>
          <div className="info-note">
            <Info size={18} />
            <p>
              Historical performance does not guarantee future accuracy.
              Updating statistical snapshots does not retrain the models or
              validate their current-season performance.
            </p>
          </div>
        </>
      )}
    </>
  );
}
