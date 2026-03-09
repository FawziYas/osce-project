"use client";

/**
 * ChecklistForm — the scoring form examiners use per-station.
 * ONLY Examiner on assigned station, active session.
 * Disable inputs when finalized (read-only view).
 */

import { useState } from "react";
import { usePermission } from "@/lib/auth";

interface ChecklistItem {
  id: number;
  text: string;
  points: number;
  scored?: number | null;
}

interface Props {
  stationId: string;
  items: ChecklistItem[];
  isFinalized?: boolean;
  onSubmit?: (scores: Record<number, number>) => void;
}

export function ChecklistForm({ stationId, items, isFinalized = false, onSubmit }: Props) {
  const { allowed: canScore, loading } = usePermission("score", "checklist", stationId);
  const { allowed: canView } = usePermission("view", "checklist", stationId);

  const [scores, setScores] = useState<Record<number, number>>(() => {
    const initial: Record<number, number> = {};
    for (const item of items) {
      initial[item.id] = item.scored ?? 0;
    }
    return initial;
  });

  // Can't even view? Remove from DOM entirely
  if (loading || !canView) return null;

  const readOnly = isFinalized || !canScore;

  function handleChange(itemId: number, value: number) {
    if (readOnly) return;
    setScores((prev) => ({ ...prev, [itemId]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!readOnly && onSubmit) {
      onSubmit(scores);
    }
  }

  return (
    <form
      className="osce-checklist-form"
      onSubmit={handleSubmit}
      aria-label="Checklist scoring form"
    >
      {isFinalized && (
        <div className="osce-alert osce-alert--info" role="alert">
          This score has been finalized and cannot be changed.
        </div>
      )}

      <table>
        <thead>
          <tr>
            <th>Checklist Item</th>
            <th>Max Points</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.text}</td>
              <td>{item.points}</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={item.points}
                  step={0.5}
                  value={scores[item.id] ?? 0}
                  onChange={(e) => handleChange(item.id, parseFloat(e.target.value) || 0)}
                  disabled={readOnly}
                  aria-label={`Score for: ${item.text}`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Submit button only when scoring is possible */}
      {canScore && !isFinalized && (
        <button type="submit" className="osce-btn-primary">
          Submit Scores
        </button>
      )}
    </form>
  );
}
