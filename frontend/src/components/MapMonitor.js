// src/components/MapMonitor.js
import React from 'react';
import { Alert } from 'antd';
import RegionMap from './RegionMap';

const MapMonitor = () => {
  const pageWrapperStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/bg/map-bg.jpg)`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundRepeat: 'no-repeat',
    backgroundAttachment: 'fixed',
    padding: '24px',
    minHeight: 'calc(100vh - 64px)'
  };

  return (
    <div style={pageWrapperStyle}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
        <RegionMap />
      </div>
    </div>
  );
};

export default MapMonitor;