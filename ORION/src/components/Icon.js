const { useEffect, useRef } = React;

const Icon = ({ name, className }) => {
    const ref = useRef(null);
    useEffect(() => {
        if (ref.current) lucide.createIcons({ targets: [ref.current] });
    }, [ref, name]);
    return <i ref={ref} data-lucide={name} className={className}></i>;
};

export default Icon;