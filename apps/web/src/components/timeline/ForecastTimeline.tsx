import { Play, Pause, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, useEffect } from "react";
import * as Slider from "@radix-ui/react-slider";
import { motion, AnimatePresence } from "framer-motion";

const FORECAST_HORIZONS = [0, 15, 30, 45, 60] as const;

interface ForecastTimelineProps {
  horizon: number;
  onHorizonChange: (horizon: number) => void;
  timestamp: string | null;
  confidence?: number | null;
}

export function ForecastTimeline({ horizon, onHorizonChange, timestamp, confidence }: ForecastTimelineProps) {
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        const currentIndex = FORECAST_HORIZONS.indexOf(horizon as typeof FORECAST_HORIZONS[number]);
        const nextIndex = (currentIndex + 1) % FORECAST_HORIZONS.length;
        onHorizonChange(FORECAST_HORIZONS[nextIndex]);
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isPlaying, horizon, onHorizonChange]);

  const currentIndex = FORECAST_HORIZONS.indexOf(horizon as typeof FORECAST_HORIZONS[number]);

  const handlePrev = () => {
    const nextIdx = currentIndex > 0 ? currentIndex - 1 : FORECAST_HORIZONS.length - 1;
    onHorizonChange(FORECAST_HORIZONS[nextIdx]);
  };

  const handleNext = () => {
    const nextIdx = currentIndex < FORECAST_HORIZONS.length - 1 ? currentIndex + 1 : 0;
    onHorizonChange(FORECAST_HORIZONS[nextIdx]);
  };

  return (
    <div className="absolute bottom-4 left-1/2 z-20 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 rounded-xl border border-slate-700/80 bg-slate-900/90 px-4 py-3 shadow-2xl backdrop-blur-xl select-none">
      <div className="mb-2 flex items-center justify-between text-sm">
        <AnimatePresence mode="wait">
          <motion.span
            key={horizon}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18 }}
            className="font-semibold text-white"
          >
            {horizon === 0 ? "Current Radar" : `Forecast +${horizon} min`}
          </motion.span>
        </AnimatePresence>
        <div className="flex items-center gap-3 text-xs">
          {confidence != null && horizon > 0 && (
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-slate-300">
              {Math.round(confidence * 100)}% conf.
            </span>
          )}
          <span className="font-mono text-slate-400">
            {timestamp ? new Date(timestamp).toLocaleTimeString() : "--:--"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-0.5">
          <button onClick={handlePrev} className="rounded-md p-1 text-slate-300 transition-colors hover:bg-slate-800">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="rounded-full bg-sky-600 p-1.5 text-white transition-colors hover:bg-sky-500"
          >
            {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="ml-0.5 h-4 w-4" />}
          </button>
          <button onClick={handleNext} className="rounded-md p-1 text-slate-300 transition-colors hover:bg-slate-800">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1">
          <Slider.Root
            className="relative flex h-5 w-full touch-none select-none items-center"
            value={[currentIndex]}
            max={FORECAST_HORIZONS.length - 1}
            step={1}
            onValueChange={(val) => onHorizonChange(FORECAST_HORIZONS[val[0]])}
          >
            <Slider.Track className="relative h-[3px] grow rounded-full bg-slate-700">
              <Slider.Range className="absolute h-full rounded-full bg-sky-500" />
            </Slider.Track>
            <Slider.Thumb
              className="block h-3.5 w-3.5 rounded-full bg-white shadow-[0_2px_10px] shadow-black/50 hover:bg-sky-50 focus:outline-none focus:ring-2 focus:ring-sky-500"
              aria-label="Forecast Horizon"
            />
          </Slider.Root>
          <div className="mt-1 flex justify-between text-[10px] font-medium text-slate-500">
            <span>Now</span>
            <span>+15</span>
            <span>+30</span>
            <span>+45</span>
            <span>+60</span>
          </div>
        </div>
      </div>
    </div>
  );
}
