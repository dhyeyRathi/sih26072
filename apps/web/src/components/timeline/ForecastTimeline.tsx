import { Play, Pause, ChevronLeft, ChevronRight } from "lucide-react";
import { useState, useEffect } from "react";
import * as Slider from '@radix-ui/react-slider';
import { cn } from "@/lib/utils";

interface ForecastTimelineProps {
  horizon: number;
  onHorizonChange: (horizon: number) => void;
  timestamp: string | null;
}

export function ForecastTimeline({ horizon, onHorizonChange, timestamp }: ForecastTimelineProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const horizons = [0, 15, 30, 45, 60];

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        onHorizonChange((prev) => {
          const currentIndex = horizons.indexOf(prev);
          const nextIndex = (currentIndex + 1) % horizons.length;
          return horizons[nextIndex];
        });
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [isPlaying, onHorizonChange, horizons]);

  const currentIndex = horizons.indexOf(horizon);

  const handlePrev = () => {
    const nextIdx = currentIndex > 0 ? currentIndex - 1 : horizons.length - 1;
    onHorizonChange(horizons[nextIdx]);
  };

  const handleNext = () => {
    const nextIdx = currentIndex < horizons.length - 1 ? currentIndex + 1 : 0;
    onHorizonChange(horizons[nextIdx]);
  };

  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-3xl bg-[#0a0e27]/80 backdrop-blur-md border border-slate-700 rounded-xl p-4 shadow-2xl flex flex-col gap-3">
      <div className="flex justify-between items-center text-sm">
        <span className="font-semibold text-white">
          {horizon === 0 ? "Current Radar" : `Forecast: +${horizon} min`}
        </span>
        <span className="text-slate-400 font-mono">
          {timestamp ? new Date(timestamp).toLocaleTimeString() : "--:--"}
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-1">
          <button 
            onClick={handlePrev}
            className="p-1.5 hover:bg-slate-800 rounded-md text-slate-300 transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          
          <button 
            onClick={() => setIsPlaying(!isPlaying)}
            className="p-2 bg-blue-600 hover:bg-blue-500 rounded-full text-white transition-colors"
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>

          <button 
            onClick={handleNext}
            className="p-1.5 hover:bg-slate-800 rounded-md text-slate-300 transition-colors"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        <Slider.Root
          className="relative flex items-center select-none touch-none w-full h-5"
          value={[currentIndex]}
          max={horizons.length - 1}
          step={1}
          onValueChange={(val) => onHorizonChange(horizons[val[0]])}
        >
          <Slider.Track className="bg-slate-700 relative grow rounded-full h-[4px]">
            <Slider.Range className="absolute bg-blue-500 rounded-full h-full" />
          </Slider.Track>
          <Slider.Thumb
            className="block w-4 h-4 bg-white shadow-[0_2px_10px] shadow-black/50 rounded-[10px] hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            aria-label="Forecast Horizon"
          />
        </Slider.Root>
      </div>

      <div className="flex justify-between text-xs text-slate-500 font-medium px-28">
        <span>Now</span>
        <span>+15</span>
        <span>+30</span>
        <span>+45</span>
        <span>+60</span>
      </div>
    </div>
  );
}
