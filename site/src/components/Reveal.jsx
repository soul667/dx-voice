import { motion } from 'framer-motion';

export default function Reveal({
  as = 'div',
  delay = 0,
  y = 22,
  className = '',
  children,
  ...rest
}) {
  const MotionTag = motion[as] ?? motion.div;
  return (
    <MotionTag
      className={className || undefined}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.14 }}
      transition={{ duration: 0.72, delay, ease: [0.19, 1, 0.22, 1] }}
      {...rest}
    >
      {children}
    </MotionTag>
  );
}
