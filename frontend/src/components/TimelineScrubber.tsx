import { Box, Slider, Text } from "@mantine/core";
import { useEffect, useRef, useState } from "react";
import { type ReplayStatus, api } from "../api";

interface Props {
  status: ReplayStatus;
  onStatusChange: (s: ReplayStatus) => void;
}

export function TimelineScrubber({ status, onStatusChange }: Props) {
  const [events, setEvents] = useState<Array<{ index: number; ts: string }>>([]);
  const [dragValue, setDragValue] = useState<number | null>(null);
  const seekingRef = useRef(false);

  useEffect(() => {
    api.replay.events().then(setEvents).catch(() => {});
  }, []);

  const handleSeek = async (idx: number) => {
    if (seekingRef.current) return;
    seekingRef.current = true;
    try {
      const s = await api.replay.seek(idx);
      onStatusChange(s);
    } finally {
      setDragValue(null);
      seekingRef.current = false;
    }
  };

  const sliderValue = dragValue ?? status.current_index;
  const total = status.total_events || 100;

  const formatLabel = (val: number) => {
    const ev = events[val];
    if (!ev) return String(val);
    return new Date(ev.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const startTs = events[0]?.ts;
  const endTs = events[events.length - 1]?.ts;

  return (
    <Box>
      <Slider
        value={sliderValue}
        min={0}
        max={total}
        onChange={setDragValue}
        onChangeEnd={handleSeek}
        label={formatLabel}
        size="sm"
        color={status.current_index >= total && total > 0 ? "green" : "blue"}
        disabled={events.length === 0}
        styles={{ thumb: { transition: "none" } }}
      />
      {startTs && endTs && (
        <Box style={{ display: "flex", justifyContent: "space-between" }} mt={2}>
          <Text size="xs" c="dimmed">
            {new Date(startTs).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </Text>
          <Text size="xs" c="dimmed">
            {status.current_index}/{total} events
          </Text>
          <Text size="xs" c="dimmed">
            {new Date(endTs).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </Text>
        </Box>
      )}
    </Box>
  );
}
