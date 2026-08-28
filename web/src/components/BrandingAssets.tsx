import React from 'react';

/**
 * Image 1: Bafang Jincai Avatar (八方进财 / 黄金万两 / 招财进宝 / 日进斗金 / 财源广进)
 * Authentically crafted Chinese seal & calligraphy talisman avatar
 */
export const BafangJincaiAvatar: React.FC<{
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}> = ({ size = 'md', className = '' }) => {
  const sizeMap = {
    sm: 'w-7 h-7 text-[8px]',
    md: 'w-9 h-9 text-[10px]',
    lg: 'w-12 h-12 text-xs',
    xl: 'w-16 h-16 text-sm',
  };

  return (
    <div
      className={`relative rounded-xl overflow-hidden shadow-md flex items-center justify-center select-none shrink-0 border border-amber-600/40 ${sizeMap[size]} ${className}`}
      title="雲頂天宮 · 八方进财"
      style={{
        background: 'linear-gradient(135deg, #e8cf9c 0%, #d8b77a 40%, #c29d5b 100%)',
      }}
    >
      {/* Textured Aged Paper Overlay */}
      <div
        className="absolute inset-0 opacity-40 mix-blend-multiply pointer-events-none"
        style={{
          backgroundImage:
            'radial-gradient(#8d6728 1px, transparent 1px), radial-gradient(#6d4a13 1px, transparent 1px)',
          backgroundSize: '8px 8px',
          backgroundPosition: '0 0, 4px 4px',
        }}
      />

      {/* Outer Border with double decorative line */}
      <div className="absolute inset-0.5 border border-red-800/30 rounded-lg pointer-events-none" />

      {/* Side Calligraphy (Left & Right) */}
      <div className="absolute left-1 top-0.5 bottom-0.5 flex flex-col justify-between text-[7px] leading-[8px] font-serif font-black text-red-900/90 scale-90 origin-left">
        <span>招</span>
        <span>财</span>
        <span>进</span>
        <span>宝</span>
      </div>

      <div className="absolute right-1 top-0.5 bottom-0.5 flex flex-col justify-between text-[7px] leading-[8px] font-serif font-black text-red-900/90 scale-90 origin-right">
        <span>黄</span>
        <span>金</span>
        <span>万</span>
        <span>两</span>
      </div>

      {/* Central Red Vermilion Stamp (八方进财) */}
      <div className="relative z-10 w-[55%] h-[82%] bg-gradient-to-b from-[#a81c1c] via-[#bd2222] to-[#8d1414] rounded border border-red-950/60 shadow-inner flex flex-col items-center justify-center p-0.5">
        <div className="w-full h-full border border-dashed border-amber-200/50 rounded-sm flex flex-col items-center justify-center text-amber-100 font-serif font-black tracking-widest text-[9px] leading-[9px] shadow-sm">
          <span className="scale-95">八</span>
          <span className="scale-95">方</span>
          <span className="scale-95">进</span>
          <span className="scale-95">财</span>
        </div>
      </div>

      {/* Auspicious Gold Gilded Glow on hover */}
      <div className="absolute inset-0 rounded-xl bg-gradient-to-tr from-amber-400/0 via-amber-300/10 to-amber-200/30 pointer-events-none" />
    </div>
  );
};

/**
 * Image 2: Laicai Background (来财 / 日进斗金 / 横财暴富 / 苍龙五路暴富 / 暴富大吉 / 金箔质感背景)
 * Semi-transparent, subtle faded calligraphy gold foil backdrop for 雲頂天宮
 */
export const LaicaiBackground: React.FC = () => {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0 overflow-hidden select-none"
      aria-hidden="true"
    >
      {/* Deep Space Slate Backdrop */}
      <div className="absolute inset-0 bg-slate-950/95" />

      {/* Subtle Gold foil texture overlay with 12% opacity */}
      <div
        className="absolute inset-0 opacity-[0.09] mix-blend-screen"
        style={{
          background: `
            radial-gradient(ellipse at 80% 20%, rgba(245, 197, 66, 0.4) 0%, transparent 50%),
            radial-gradient(ellipse at 20% 80%, rgba(212, 160, 23, 0.3) 0%, transparent 60%),
            linear-gradient(135deg, rgba(184, 134, 11, 0.15) 0%, rgba(0, 0, 0, 0) 100%)
          `,
        }}
      />

      {/* Central Majestic Watermark of Image 2 (来财 + Auspicious Calligraphy) */}
      <div className="absolute right-4 md:right-20 top-1/2 -translate-y-1/2 w-[340px] md:w-[540px] opacity-[0.07] flex flex-col items-center justify-center transform rotate-[-4deg]">
        <svg
          viewBox="0 0 400 400"
          className="w-full h-full fill-current text-amber-300"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Imperial Square Seal Stamp Behind Calligraphy */}
          <rect
            x="110"
            y="110"
            width="180"
            height="180"
            rx="12"
            fill="#a81c1c"
            fillOpacity="0.4"
            stroke="#e8cf9c"
            strokeWidth="3"
            strokeDasharray="4 2"
          />

          {/* Calligraphy Characters "来 财" */}
          <text
            x="200"
            y="190"
            textAnchor="middle"
            fontFamily="Noto Serif SC, Songti SC, serif"
            fontWeight="900"
            fontSize="100"
            fill="#f5c542"
            letterSpacing="2"
          >
            来
          </text>
          <text
            x="200"
            y="290"
            textAnchor="middle"
            fontFamily="Noto Serif SC, Songti SC, serif"
            fontWeight="900"
            fontSize="100"
            fill="#f5c542"
            letterSpacing="2"
          >
            財
          </text>

          {/* Left Auspicious Verses */}
          <g
            fontSize="16"
            fontFamily="Noto Serif SC, serif"
            fontWeight="bold"
            fill="#e8cf9c"
            opacity="0.85"
          >
            <text x="35" y="100">财源滚滚</text>
            <text x="35" y="140">正财暴富</text>
            <text x="35" y="180">八方暴富</text>
            <text x="35" y="220">发财暴富</text>
            <text x="35" y="260">财源广进</text>
          </g>

          {/* Right Auspicious Verses */}
          <g
            fontSize="16"
            fontFamily="Noto Serif SC, serif"
            fontWeight="bold"
            fill="#e8cf9c"
            opacity="0.85"
          >
            <text x="315" y="90">日进斗金</text>
            <text x="315" y="130">横财暴富</text>
            <text x="315" y="170">苍龙五路</text>
            <text x="315" y="210">暴富大吉</text>
            <text x="315" y="250">黄金万两</text>
          </g>

          {/* Celestial Constellation Lines */}
          <circle cx="90" cy="50" r="3" fill="#f5c542" />
          <circle cx="130" cy="35" r="3" fill="#f5c542" />
          <circle cx="160" cy="65" r="3" fill="#f5c542" />
          <line x1="90" y1="50" x2="130" y2="35" stroke="#f5c542" strokeWidth="1" strokeDasharray="2 2" />
          <line x1="130" y1="35" x2="160" y2="65" stroke="#f5c542" strokeWidth="1" strokeDasharray="2 2" />
          <text x="95" y="35" fontSize="10" fill="#f5c542" fontFamily="serif">朱雀</text>

          <circle cx="270" cy="40" r="3" fill="#f5c542" />
          <circle cx="310" cy="55" r="3" fill="#f5c542" />
          <line x1="270" y1="40" x2="310" y2="55" stroke="#f5c542" strokeWidth="1" strokeDasharray="2 2" />
          <text x="275" y="30" fontSize="10" fill="#f5c542" fontFamily="serif">玄武</text>
        </svg>
      </div>

      {/* Grid Scanlines for Tech Aesthetic */}
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            'linear-gradient(to right, #00ffff 1px, transparent 1px), linear-gradient(to bottom, #00ffff 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />
    </div>
  );
};
