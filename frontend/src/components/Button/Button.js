import React from 'react';
import './Button.css';

const Button = ({ children, onClick, type, disabled }) => {
  return (
    <button
      className={`button ${type}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};

export default Button;
