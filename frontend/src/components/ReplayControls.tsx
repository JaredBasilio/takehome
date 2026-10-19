import {
  Badge,
  Box,
  Button,
  Group,
  SegmentedControl,
  Text,
} from "@mantine/core";
import {
  IconPlayerPause,
  IconPlayerPlay,
  IconRefresh,
} from "@tabler/icons-react";
import { useState } from "react";
import { type ReplayStatus, api } from "../api";

interface Props {
  status: ReplayStatus;
  onStatusChange: (s: ReplayStatus) => void;
}

export function ReplayControls({ status, onStatusChange }: Props) {
  const [speed, setSpeed] = useState("normal");

  const handleStart = async () => {
    const s = await api.replay.start(speed);
    onStatusChange(s);
  };

  const handleReset = async () => {
    const s = await api.replay.reset();
    onStatusChange(s);
  };

  const isDone =
    !status.is_running && status.current_index > 0 && status.current_index >= status.total_events;

  return (
    <Group gap="sm" align="center">
      {status.current_ts && (
        <Box style={{ minWidth: 100 }}>
          <Text size="xs" c="dimmed" lh={1}>
            Sim time
          </Text>
          <Text size="xs" fw={600} ff="monospace">
            {new Date(status.current_ts).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </Text>
        </Box>
      )}

      <SegmentedControl
        size="xs"
        value={speed}
        onChange={setSpeed}
        disabled={status.is_running}
        data={[
          { label: "Slow", value: "slow" },
          { label: "Normal", value: "normal" },
          { label: "Fast", value: "fast" },
          { label: "Instant", value: "instant" },
        ]}
      />

      {!status.is_running && !isDone && (
        <Button
          size="xs"
          leftSection={<IconPlayerPlay size={14} />}
          onClick={handleStart}
          disabled={status.current_index >= status.total_events && status.total_events > 0}
        >
          Play
        </Button>
      )}

      {status.is_running && (
        <Badge color="green" variant="dot" size="sm">
          Running
        </Badge>
      )}

      {isDone && (
        <Badge color="blue" variant="light" size="sm">
          Done
        </Badge>
      )}

      <Button
        size="xs"
        variant="subtle"
        color="gray"
        leftSection={<IconRefresh size={14} />}
        onClick={handleReset}
      >
        Reset
      </Button>
    </Group>
  );
}
